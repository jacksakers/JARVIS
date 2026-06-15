"""
Development Intern skills — give JARVIS the ability to read, search, and
edit local Git repositories inside a sandboxed development root directory.

All file-system operations validate that the resolved path stays inside
DEV_ROOT_DIR (config.yaml → development.root_dir) to prevent traversal.

Workflow JARVIS follows:
  1. dev_list_repos       → see what projects exist
  2. dev_list_tree        → explore project structure
  3. dev_search_codebase  → find relevant files
  4. dev_read_file        → read exact content (with line numbers)
  5. dev_create_branch    → create feature branch (NEVER edits main/master)
  6. dev_edit_file        → targeted search-and-replace edits
  7. dev_commit_pr        → stage + commit + create PR record for user review
"""
import os
import subprocess
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field

from app.skills.base_skill import BaseSkill
from app.config import load_config

# Directories to ignore when listing trees or searching
_IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", "venv", ".venv",
    "dist", "build", ".next", ".cache", "coverage", ".mypy_cache",
}


# ── Path helpers ──────────────────────────────────────────────────────────────

def _get_dev_root() -> Path:
    cfg = load_config()
    root = cfg.get("development", {}).get("root_dir", "")
    if not root:
        raise ValueError(
            "Development root not configured. "
            "Add 'development.root_dir' to config.yaml."
        )
    return Path(root).resolve()


def _repo_path(repo_name: str) -> Path:
    """Resolve and validate the repo path is inside DEV_ROOT_DIR."""
    dev_root = _get_dev_root()
    # Strip path separators to prevent traversal
    safe_name = Path(repo_name).name
    repo_root = (dev_root / safe_name).resolve()
    if not str(repo_root).startswith(str(dev_root)):
        raise ValueError(f"Access denied: '{repo_name}' is outside the development root.")
    if not repo_root.exists():
        raise ValueError(f"Repository '{repo_name}' not found in {dev_root}.")
    return repo_root


def _file_path(repo_name: str, rel_path: str) -> Path:
    """Resolve and validate a file path within a repo."""
    repo_root = _repo_path(repo_name)
    full = (repo_root / rel_path).resolve()
    if not str(full).startswith(str(repo_root)):
        raise ValueError("Access denied: path traversal detected.")
    return full


def _run_git(args: list, cwd: Path):
    """Run a git command; returns (returncode, stdout, stderr)."""
    result = subprocess.run(
        ["git"] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


# ── Input models ──────────────────────────────────────────────────────────────

class DevListReposInput(BaseModel):
    pass


class DevListTreeInput(BaseModel):
    repo_name: str = Field(description="Repository folder name inside DEV_ROOT_DIR")
    path: str = Field(default=".", description="Sub-path to list (default: root)")


class DevReadFileInput(BaseModel):
    repo_name: str = Field(description="Repository folder name")
    file_path: str = Field(description="Relative file path within the repository")
    start_line: Optional[int] = Field(default=None, description="First line to read (1-indexed)")
    end_line: Optional[int] = Field(default=None, description="Last line to read (1-indexed)")


class DevSearchCodebaseInput(BaseModel):
    repo_name: str = Field(description="Repository folder name")
    query: str = Field(description="Text to search for (case-insensitive)")
    file_pattern: str = Field(default="*", description="File suffix filter (e.g. '*.py', '*.tsx')")


class DevCreateBranchInput(BaseModel):
    repo_name: str = Field(description="Repository folder name")
    branch_name: str = Field(description="Feature branch name, e.g. 'jarvis/add-login-page'")


class DevEditFileInput(BaseModel):
    repo_name: str = Field(description="Repository folder name")
    file_path: str = Field(description="Relative file path within the repository")
    search_block: str = Field(
        description="The EXACT existing text to replace (must match file content including all whitespace)"
    )
    replace_block: str = Field(description="New text to insert in place of search_block")


class DevCommitPRInput(BaseModel):
    repo_name: str = Field(description="Repository folder name")
    commit_message: str = Field(description="Clear, descriptive commit message")


# ── Skills ────────────────────────────────────────────────────────────────────

class DevListRepositories(BaseSkill):
    name = "dev_list_repos"
    description = (
        "List all available local Git repositories in the development root directory. "
        "Call this first to see what projects are available."
    )
    input_model = DevListReposInput

    def execute(self, params: DevListReposInput) -> str:
        try:
            dev_root = _get_dev_root()
        except ValueError as e:
            return f"Error: {e}"

        if not dev_root.exists():
            return f"Error: Development root '{dev_root}' does not exist."

        repos = []
        for item in sorted(dev_root.iterdir()):
            if item.is_dir() and (item / ".git").exists():
                rc, branch, _ = _run_git(["branch", "--show-current"], item)
                branch_name = branch.strip() if rc == 0 else "unknown"
                repos.append(f"- {item.name}  (current branch: {branch_name})")

        if not repos:
            return f"No Git repositories found in {dev_root}."
        return "Available repositories:\n" + "\n".join(repos)


class DevListTree(BaseSkill):
    name = "dev_list_tree"
    description = (
        "List the directory tree of a repository or subdirectory. "
        "Skips .git, node_modules, __pycache__, venv, and build artifacts. "
        "Use this to understand project structure before reading files."
    )
    input_model = DevListTreeInput

    def execute(self, params: DevListTreeInput) -> str:
        try:
            if params.path in (".", ""):
                base_path = _repo_path(params.repo_name)
            else:
                base_path = _file_path(params.repo_name, params.path)
        except ValueError as e:
            return f"Error: {e}"

        if not base_path.exists():
            return f"Path '{params.path}' not found in '{params.repo_name}'."

        lines: list = []
        self._walk(base_path, base_path, lines, depth=0)

        if not lines:
            return f"Directory '{params.path}' is empty."
        return (
            f"Tree of {params.repo_name}/{params.path}:\n"
            + "\n".join(lines[:300])
        )

    def _walk(self, base: Path, path: Path, lines: list, depth: int) -> None:
        if depth > 5:
            return
        try:
            items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))
        except PermissionError:
            return
        for item in items:
            if item.name in _IGNORE_DIRS or item.name.startswith("."):
                continue
            indent = "  " * depth
            if item.is_dir():
                lines.append(f"{indent}{item.name}/")
                self._walk(base, item, lines, depth + 1)
            else:
                lines.append(f"{indent}{item.name}")


class DevReadFile(BaseSkill):
    name = "dev_read_file"
    description = (
        "Read a file from a repository with line numbers. "
        "Use start_line/end_line to read only a section (max 300 lines at a time). "
        "Always read a file before editing it."
    )
    input_model = DevReadFileInput

    def execute(self, params: DevReadFileInput) -> str:
        try:
            full_path = _file_path(params.repo_name, params.file_path)
        except ValueError as e:
            return f"Error: {e}"

        if not full_path.exists():
            return f"File '{params.file_path}' not found in '{params.repo_name}'."
        if not full_path.is_file():
            return f"'{params.file_path}' is not a file."

        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"Error reading file: {e}"

        lines = content.splitlines()
        total = len(lines)
        start = max(1, params.start_line or 1) - 1
        end = min(total, params.end_line or total)
        if end - start > 300:
            end = start + 300

        numbered = [
            f"{i + 1:5d} | {line}"
            for i, line in enumerate(lines[start:end], start=start)
        ]
        return (
            f"File: {params.repo_name}/{params.file_path} "
            f"(lines {start + 1}–{end} of {total})\n\n"
            + "\n".join(numbered)
        )


class DevSearchCodebase(BaseSkill):
    name = "dev_search_codebase"
    description = (
        "Search for a text string across all files in a repository (case-insensitive). "
        "Returns file paths and matching line snippets. "
        "Use this to find where specific functionality, classes, or variables live."
    )
    input_model = DevSearchCodebaseInput

    def execute(self, params: DevSearchCodebaseInput) -> str:
        try:
            repo_root = _repo_path(params.repo_name)
        except ValueError as e:
            return f"Error: {e}"

        results = []
        query_lower = params.query.lower()
        suffix_filter = params.file_pattern.lstrip("*") if params.file_pattern != "*" else None

        for root, dirs, files in os.walk(repo_root):
            dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS and not d.startswith(".")]
            for fname in sorted(files):
                if suffix_filter and not fname.endswith(suffix_filter):
                    continue
                fpath = Path(root) / fname
                try:
                    text = fpath.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                for lineno, line in enumerate(text.splitlines(), 1):
                    if query_lower in line.lower():
                        rel = str(fpath.relative_to(repo_root))
                        results.append(f"{rel}:{lineno}: {line.strip()[:120]}")
                if len(results) >= 50:
                    break
            if len(results) >= 50:
                break

        if not results:
            return f"No matches for '{params.query}' in {params.repo_name}."
        header = f"Found {len(results)} match(es) for '{params.query}' in {params.repo_name}:"
        return header + "\n" + "\n".join(results)


class DevCreateBranch(BaseSkill):
    name = "dev_create_branch"
    description = (
        "Create a new Git feature branch. "
        "Always branch before editing files. "
        "Use the format 'jarvis/<feature-name>' (e.g. 'jarvis/add-login-page'). "
        "You cannot create a branch named 'main' or 'master'."
    )
    input_model = DevCreateBranchInput

    def execute(self, params: DevCreateBranchInput) -> str:
        try:
            repo_root = _repo_path(params.repo_name)
        except ValueError as e:
            return f"Error: {e}"

        if params.branch_name in ("main", "master"):
            return "Error: Cannot create a branch named 'main' or 'master'."

        rc, current, _ = _run_git(["branch", "--show-current"], repo_root)
        current_branch = current.strip()

        rc, out, err = _run_git(["checkout", "-b", params.branch_name], repo_root)
        if rc != 0:
            # Maybe it already exists; try switching to it
            rc2, out2, err2 = _run_git(["checkout", params.branch_name], repo_root)
            if rc2 != 0:
                return f"Error creating branch '{params.branch_name}': {err.strip()}"
            return f"Switched to existing branch: {params.branch_name}"

        return (
            f"Created and switched to branch: {params.branch_name} "
            f"(previously on {current_branch})"
        )


class DevEditFile(BaseSkill):
    name = "dev_edit_file"
    description = (
        "Edit a file by replacing an exact block of text with new content. "
        "search_block must exactly match the existing file content (whitespace included). "
        "Always call dev_read_file before using this tool so you have the exact text."
    )
    input_model = DevEditFileInput

    def execute(self, params: DevEditFileInput) -> str:
        try:
            full_path = _file_path(params.repo_name, params.file_path)
        except ValueError as e:
            return f"Error: {e}"

        if not full_path.exists():
            return f"File '{params.file_path}' not found in '{params.repo_name}'."

        try:
            original = full_path.read_text(encoding="utf-8")
        except Exception as e:
            return f"Error reading file: {e}"

        if params.search_block not in original:
            return (
                f"Error: search_block not found in '{params.file_path}'. "
                "The block must match exactly — check whitespace and indentation. "
                "Re-read the file with dev_read_file and try again."
            )

        count = original.count(params.search_block)
        if count > 1:
            return (
                f"Error: search_block appears {count} times in '{params.file_path}'. "
                "Add more surrounding context to make it unique."
            )

        new_content = original.replace(params.search_block, params.replace_block, 1)
        try:
            full_path.write_text(new_content, encoding="utf-8")
        except Exception as e:
            return f"Error writing file: {e}"

        return f"Successfully updated '{params.repo_name}/{params.file_path}'."


class DevCommitPR(BaseSkill):
    name = "dev_commit_pr"
    description = (
        "Stage ALL changes, commit them, and create a Pull Request for user review. "
        "Call this only after all edits are complete. "
        "The user will see a colored diff in the Development tab and can merge or discard."
    )
    input_model = DevCommitPRInput

    def execute(self, params: DevCommitPRInput) -> str:
        try:
            repo_root = _repo_path(params.repo_name)
        except ValueError as e:
            return f"Error: {e}"

        rc, branch_out, _ = _run_git(["branch", "--show-current"], repo_root)
        current_branch = branch_out.strip()
        if current_branch in ("main", "master"):
            return "Error: Cannot commit to main/master. Create a feature branch first."

        # Stage all
        rc, _, err = _run_git(["add", "-A"], repo_root)
        if rc != 0:
            return f"Error staging changes: {err.strip()}"

        # Check for anything to commit
        rc, status_out, _ = _run_git(["status", "--porcelain"], repo_root)
        if not status_out.strip():
            return "Nothing to commit — working tree is clean."

        # Commit
        rc, _, err = _run_git(["commit", "-m", params.commit_message], repo_root)
        if rc != 0:
            return f"Error committing: {err.strip()}"

        # Generate diff against base branch
        base = "main"
        rc2, _, _ = _run_git(["rev-parse", "--verify", "main"], repo_root)
        if rc2 != 0:
            base = "master"
        rc, diff_out, _ = _run_git(["diff", f"{base}...{current_branch}"], repo_root)
        diff_text = diff_out[:50000] if rc == 0 else "(diff unavailable)"

        # Get task_id from thread-local context
        try:
            from app.skills.ask_user_skill import _current_task
            task_id = getattr(_current_task, "task_id", None)
        except Exception:
            task_id = None

        try:
            from app.database import session_scope
            from app.models import DevPullRequest

            with session_scope() as session:
                pr = DevPullRequest(
                    project_name=params.repo_name,
                    branch_name=current_branch,
                    task_id=task_id,
                    commit_message=params.commit_message,
                    diff=diff_text,
                )
                session.add(pr)
                session.flush()
                pr_id = pr.id

            from app.worker.connection_manager import manager
            manager.broadcast_from_thread(
                "dev_pr_created",
                {
                    "pr_id": pr_id,
                    "project_name": params.repo_name,
                    "branch_name": current_branch,
                },
            )

            return (
                f"Pull Request #{pr_id} created and ready for review.\n"
                f"Branch: {current_branch}\n"
                f"Commit: {params.commit_message}\n"
                "Open the Development tab to review the diff, then merge or request changes."
            )
        except Exception as e:
            return (
                f"Changes committed to '{current_branch}', "
                f"but failed to record PR in database: {e}"
            )
