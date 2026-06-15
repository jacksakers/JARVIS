"""
API router: Development Intern feature.
Endpoints for project listing, PR management, and dev task submission.
"""
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.config import load_config
from app.database import get_session
from app.models import DevPRStatus, DevPullRequest, Task, TaskStatus, User

router = APIRouter(prefix="/dev", tags=["development"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_dev_root() -> Path:
    cfg = load_config()
    root = cfg.get("development", {}).get("root_dir", "")
    if not root:
        raise HTTPException(
            status_code=503,
            detail="Development root not configured. Add 'development.root_dir' to config.yaml.",
        )
    p = Path(root).resolve()
    if not p.exists():
        raise HTTPException(status_code=503, detail=f"Development root '{p}' does not exist.")
    return p


def _repo_path(repo_name: str) -> Path:
    dev_root = _get_dev_root()
    safe_name = Path(repo_name).name  # strip traversal attempts
    repo_root = (dev_root / safe_name).resolve()
    if not str(repo_root).startswith(str(dev_root)):
        raise HTTPException(status_code=403, detail="Path traversal detected.")
    if not repo_root.exists():
        raise HTTPException(status_code=404, detail=f"Repository '{repo_name}' not found.")
    return repo_root


def _run_git(args: list, cwd: Path):
    result = subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


def _get_default_user(session: Session) -> User:
    user = session.exec(select(User).where(User.is_primary == True)).first()
    if not user:
        raise HTTPException(status_code=404, detail="No primary user found.")
    return user


_DEV_SKILL_NAMES = [
    "dev_list_repos",
    "dev_list_tree",
    "dev_read_file",
    "dev_search_codebase",
    "dev_create_branch",
    "dev_edit_file",
    "dev_write_file",
    "dev_commit_pr",
]

_DEV_SYSTEM_PROMPT = (
    "You are JARVIS acting as a senior software developer intern. "
    "You have been given a specific coding task for a local repository.\n\n"
    "Follow this EXACT workflow — do not skip steps:\n"
    "1. Call dev_list_tree to understand the project structure\n"
    "2. Call dev_search_codebase to find files relevant to the task\n"
    "3. Call dev_read_file to read specific files (ALWAYS read before editing)\n"
    "4. Call dev_create_branch to create a feature branch (format: 'jarvis/<feature>')\n"
    "5. Make your changes using dev_edit_file (line-number edits) or dev_write_file (new files)\n"
    "6. Repeat steps 3 and 5 for all required changes, re-reading after each edit to verify\n"
    "7. Call dev_commit_pr with a clear commit message when all edits are complete\n\n"
    "HOW TO EDIT FILES (important):\n"
    "- dev_read_file shows line numbers like '   42 | code here'. Use those numbers.\n"
    "- dev_edit_file(start_line, end_line, new_content): replaces lines start–end with new_content.\n"
    "  Example: to replace line 42 only, use start_line=42, end_line=42.\n"
    "  Example: to insert after line 10 without replacing anything, use start_line=11, end_line=10.\n"
    "  Example: to append to end of a 50-line file, use start_line=51, end_line=50.\n"
    "- dev_write_file(file_path, content): creates a brand-new file or overwrites entirely.\n"
    "  Use this for new files only — use dev_edit_file for changes to existing files.\n\n"
    "RULES:\n"
    "- Never edit files on main or master — always create a feature branch first\n"
    "- Always read a file before editing it to get current line numbers\n"
    "- Re-read the file after editing to confirm the change was applied correctly\n"
    "- Make minimal, focused changes that address only the requested feature\n"
    "- After dev_commit_pr succeeds, summarise what you changed and why"
)


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/active-task")
def get_active_dev_task(session: Session = Depends(get_session)):
    """
    Return the most recent queued/running dev task, plus any pending PR for
    the same project. Used by the frontend to restore state after navigation.
    """
    from sqlmodel import or_
    task = session.exec(
        select(Task)
        .where(
            Task.allowed_skill_names_override.is_not(None),
            or_(Task.status == TaskStatus.queued, Task.status == TaskStatus.running),
        )
        .order_by(Task.created_at.desc())
        .limit(1)
    ).first()

    result: dict = {"task": None, "pr": None}

    if task:
        import json as _json
        try:
            skill_names = _json.loads(task.allowed_skill_names_override or "[]")
            if "dev_list_repos" not in skill_names:
                task = None
        except Exception:
            task = None

    if task:
        result["task"] = {
            "id": task.id,
            "status": task.status,
            "prompt": task.prompt[:200],
            "created_at": task.created_at.isoformat(),
        }
        # Extract project name from prompt (format: "Repository: <name>\n\n...")
        project_name = None
        for line in task.prompt.splitlines():
            if line.startswith("Repository:"):
                project_name = line.split(":", 1)[1].strip()
                break
        if project_name:
            result["task"]["project_name"] = project_name
            pr = session.exec(
                select(DevPullRequest)
                .where(
                    DevPullRequest.project_name == project_name,
                    DevPullRequest.status == "pending",
                )
                .order_by(DevPullRequest.created_at.desc())
                .limit(1)
            ).first()
            if pr:
                result["pr"] = {
                    "id": pr.id,
                    "project_name": pr.project_name,
                    "branch_name": pr.branch_name,
                    "status": pr.status,
                    "commit_message": pr.commit_message,
                }

    return result


@router.get("/projects")
def list_projects():
    """Return all Git repositories inside the development root."""
    dev_root = _get_dev_root()
    projects = []
    for item in sorted(dev_root.iterdir()):
        if not item.is_dir() or not (item / ".git").exists():
            continue
        rc, branch, _ = _run_git(["branch", "--show-current"], item)
        rc2, log_out, _ = _run_git(["log", "-1", "--format=%h %s"], item)
        projects.append(
            {
                "name": item.name,
                "path": str(item),
                "branch": branch.strip() if rc == 0 else "unknown",
                "last_commit": log_out.strip() if rc2 == 0 else "",
            }
        )
    return projects


@router.get("/projects/{repo_name}/tree")
def get_project_tree(repo_name: str, path: str = "."):
    """Return a text directory tree for the given repo / subdirectory."""
    from app.skills.dev_skills import DevListTree, DevListTreeInput

    skill = DevListTree()
    result = skill.execute(DevListTreeInput(repo_name=repo_name, path=path))
    return {"tree": result}


@router.get("/prs")
def list_prs(session: Session = Depends(get_session)):
    """List all dev pull requests (newest first)."""
    prs = session.exec(
        select(DevPullRequest).order_by(DevPullRequest.created_at.desc())
    ).all()
    return [
        {
            "id": pr.id,
            "project_name": pr.project_name,
            "branch_name": pr.branch_name,
            "status": pr.status,
            "commit_message": pr.commit_message,
            "task_id": pr.task_id,
            "created_at": pr.created_at.isoformat(),
        }
        for pr in prs
    ]


@router.get("/prs/{pr_id}")
def get_pr(pr_id: int, session: Session = Depends(get_session)):
    """Return PR details including the full diff."""
    pr = session.get(DevPullRequest, pr_id)
    if not pr:
        raise HTTPException(status_code=404, detail="PR not found.")

    diff = pr.diff
    if not diff:
        try:
            repo_root = _repo_path(pr.project_name)
            base = "main"
            rc, _, _ = _run_git(["rev-parse", "--verify", "main"], repo_root)
            if rc != 0:
                base = "master"
            rc, diff_out, _ = _run_git(["diff", f"{base}...{pr.branch_name}"], repo_root)
            diff = diff_out if rc == 0 else "(diff unavailable)"
        except Exception:
            diff = "(diff unavailable)"

    return {
        "id": pr.id,
        "project_name": pr.project_name,
        "branch_name": pr.branch_name,
        "status": pr.status,
        "commit_message": pr.commit_message,
        "task_id": pr.task_id,
        "diff": diff,
        "created_at": pr.created_at.isoformat(),
    }


@router.post("/prs/{pr_id}/merge")
def merge_pr(pr_id: int, session: Session = Depends(get_session)):
    """Merge the PR branch into main/master and delete the feature branch."""
    pr = session.get(DevPullRequest, pr_id)
    if not pr:
        raise HTTPException(status_code=404, detail="PR not found.")
    if pr.status != DevPRStatus.pending:
        raise HTTPException(status_code=400, detail=f"PR is already {pr.status.value}.")

    repo_root = _repo_path(pr.project_name)

    base = "main"
    rc, _, _ = _run_git(["rev-parse", "--verify", "main"], repo_root)
    if rc != 0:
        base = "master"

    rc, _, err = _run_git(["checkout", base], repo_root)
    if rc != 0:
        raise HTTPException(status_code=500, detail=f"Failed to checkout {base}: {err.strip()}")

    rc, _, err = _run_git(
        ["merge", "--no-ff", pr.branch_name, "-m", f"Merge {pr.branch_name}"],
        repo_root,
    )
    if rc != 0:
        raise HTTPException(status_code=500, detail=f"Merge failed: {err.strip()}")

    _run_git(["branch", "-d", pr.branch_name], repo_root)

    pr.status = DevPRStatus.merged
    pr.updated_at = datetime.now(timezone.utc)
    session.add(pr)
    session.commit()

    return {"message": f"Merged '{pr.branch_name}' into {base} and deleted branch."}


@router.post("/prs/{pr_id}/discard")
def discard_pr(pr_id: int, session: Session = Depends(get_session)):
    """Checkout main/master and force-delete the feature branch."""
    pr = session.get(DevPullRequest, pr_id)
    if not pr:
        raise HTTPException(status_code=404, detail="PR not found.")
    if pr.status != DevPRStatus.pending:
        raise HTTPException(status_code=400, detail=f"PR is already {pr.status.value}.")

    repo_root = _repo_path(pr.project_name)

    base = "main"
    rc, _, _ = _run_git(["rev-parse", "--verify", "main"], repo_root)
    if rc != 0:
        base = "master"

    _run_git(["checkout", base], repo_root)
    rc, _, err = _run_git(["branch", "-D", pr.branch_name], repo_root)
    if rc != 0:
        raise HTTPException(status_code=500, detail=f"Could not delete branch: {err.strip()}")

    pr.status = DevPRStatus.discarded
    pr.updated_at = datetime.now(timezone.utc)
    session.add(pr)
    session.commit()

    return {"message": f"Discarded '{pr.branch_name}' — returned to {base}."}


@router.post("/prs/{pr_id}/request-changes")
def request_changes(pr_id: int, payload: dict, session: Session = Depends(get_session)):
    """Queue a new task so JARVIS revises the same branch based on feedback."""
    pr = session.get(DevPullRequest, pr_id)
    if not pr:
        raise HTTPException(status_code=404, detail="PR not found.")
    if pr.status != DevPRStatus.pending:
        raise HTTPException(status_code=400, detail=f"PR is already {pr.status.value}.")

    feedback = payload.get("feedback", "").strip()
    if not feedback:
        raise HTTPException(status_code=422, detail="feedback is required.")

    user = _get_default_user(session)

    # Switch repo back to the feature branch so JARVIS picks up where it left off
    try:
        repo_root = _repo_path(pr.project_name)
        _run_git(["checkout", pr.branch_name], repo_root)
    except Exception:
        pass  # Worker will handle branch context

    task = Task(
        user_id=user.id,
        prompt=(
            f"[Change Request — PR #{pr_id}, branch: {pr.branch_name}]\n"
            f"Repository: {pr.project_name}\n\n"
            f"The user reviewed your changes and requests the following adjustments:\n"
            f"{feedback}\n\n"
            f"The branch '{pr.branch_name}' is already checked out. "
            "Read the relevant files, make the requested changes, then call dev_commit_pr."
        ),
        system_prompt_override=_DEV_SYSTEM_PROMPT,
        allowed_skill_names_override=json.dumps(_DEV_SKILL_NAMES),
        status=TaskStatus.queued,
    )
    session.add(task)
    session.commit()
    session.refresh(task)

    from app.worker.connection_manager import manager
    manager.broadcast_from_thread(
        "task_queued",
        {"task_id": task.id, "prompt": f"Change request for PR #{pr_id}"},
    )

    return {"task_id": task.id, "message": "Change request queued."}


@router.post("/task", status_code=status.HTTP_201_CREATED)
def create_dev_task(payload: dict, session: Session = Depends(get_session)):
    """Submit a development task. JARVIS will work through the feature autonomously."""
    project_name = payload.get("project_name", "").strip()
    description = payload.get("description", "").strip()

    if not project_name:
        raise HTTPException(status_code=422, detail="project_name is required.")
    if not description:
        raise HTTPException(status_code=422, detail="description is required.")

    _repo_path(project_name)  # validate project exists
    user = _get_default_user(session)

    task = Task(
        user_id=user.id,
        prompt=(
            f"Repository: {project_name}\n\n"
            f"Feature request: {description}\n\n"
            "Work through the development workflow: explore → search → read → branch → edit → commit PR."
        ),
        system_prompt_override=_DEV_SYSTEM_PROMPT,
        allowed_skill_names_override=json.dumps(_DEV_SKILL_NAMES),
        status=TaskStatus.queued,
    )
    session.add(task)
    session.commit()
    session.refresh(task)

    from app.worker.connection_manager import manager
    manager.broadcast_from_thread(
        "task_queued",
        {"task_id": task.id, "prompt": description[:100]},
    )

    return {"task_id": task.id, "project_name": project_name}
