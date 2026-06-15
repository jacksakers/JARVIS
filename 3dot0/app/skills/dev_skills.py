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
    start_line: int = Field(
        description=(
            "First line to replace (1-indexed, inclusive). "
            "Use the line numbers shown by dev_read_file."
        )
    )
    end_line: int = Field(
        description=(
            "Last line to replace (1-indexed, inclusive). "
            "Set equal to start_line to replace a single line. "
            "Set to start_line - 1 to insert without replacing any lines."
        )
    )
    new_content: str = Field(
        description=(
            "Replacement text for lines start_line through end_line. "
            "Must include proper indentation. "
            "Use an empty string to delete those lines entirely."
        )
    )


class DevWriteFileInput(BaseModel):
    repo_name: str = Field(description="Repository folder name")
    file_path: str = Field(description="Relative file path within the repository")
    content: str = Field(description="Full content to write to the file (creates or overwrites)")


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
        "Returns exact phrase matches first, then related keyword matches for any individual "
        "word in the query (words shorter than 3 characters are ignored as keywords). "
        "Use this to find where specific functionality, classes, or variables live."
    )
    input_model = DevSearchCodebaseInput

    def execute(self, params: DevSearchCodebaseInput) -> str:
        try:
            repo_root = _repo_path(params.repo_name)
        except ValueError as e:
            return f"Error: {e}"

        query_lower = params.query.lower()
        keywords = [w for w in query_lower.split() if len(w) >= 3]
        suffix_filter = params.file_pattern.lstrip("*") if params.file_pattern != "*" else None

        exact_results: list[str] = []
        keyword_results: list[str] = []
        # Track (file, lineno) pairs already captured as exact matches
        exact_seen: set[tuple[str, int]] = set()

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
                rel = str(fpath.relative_to(repo_root))
                for lineno, line in enumerate(text.splitlines(), 1):
                    line_lower = line.lower()
                    if query_lower in line_lower:
                        exact_seen.add((rel, lineno))
                        if len(exact_results) < 50:
                            exact_results.append(f"  {rel}:{lineno}: {line.strip()[:120]}")
                    elif keywords and (rel, lineno) not in exact_seen:
                        if any(kw in line_lower for kw in keywords):
                            if len(keyword_results) < 30:
                                keyword_results.append(f"  {rel}:{lineno}: {line.strip()[:120]}")

            if len(exact_results) >= 50 and len(keyword_results) >= 30:
                break

        if not exact_results and not keyword_results:
            return f"No matches for '{params.query}' in {params.repo_name}."

        parts: list[str] = []
        if exact_results:
            parts.append(f"Exact matches ({len(exact_results)}):\n" + "\n".join(exact_results))
        if keyword_results:
            parts.append(f"Related keyword matches ({len(keyword_results)}):\n" + "\n".join(keyword_results))

        return f"Search results for '{params.query}' in {params.repo_name}:\n\n" + "\n\n".join(parts)


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
        "Edit a file by replacing a range of lines with new content, using line numbers. "
        "Always call dev_read_file first to see the current line numbers. "
        "start_line and end_line are the 1-indexed line numbers to replace (inclusive). "
        "To insert lines without removing anything, set end_line = start_line - 1. "
        "To delete lines, set new_content to an empty string. "
        "This is the ONLY way to edit existing files — do NOT use dev_write_file for edits."
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

        lines = original.splitlines(keepends=True)
        total = len(lines)

        # Validate line numbers
        if params.start_line < 1:
            return f"Error: start_line must be >= 1 (got {params.start_line})."
        if params.end_line < params.start_line - 1:
            return f"Error: end_line ({params.end_line}) must be >= start_line - 1 ({params.start_line - 1})."
        if params.start_line > total + 1:
            return (
                f"Error: start_line ({params.start_line}) is beyond end of file ({total} lines). "
                f"To append to the file use start_line={total + 1}, end_line={total}."
            )

        # Build new file content
        # Lines before the replacement range (0-indexed: 0 .. start_line-2)
        before = lines[: params.start_line - 1]
        # Lines after the replacement range (0-indexed: end_line .. end)
        after = lines[params.end_line :] if params.end_line <= total else []

        # Ensure new_content ends with a newline if it's non-empty and file has trailing newlines
        replacement = params.new_content
        if replacement and not replacement.endswith("\n"):
            replacement += "\n"

        new_file = "".join(before) + replacement + "".join(after)

        try:
            full_path.write_text(new_file, encoding="utf-8")
        except Exception as e:
            return f"Error writing file: {e}"

        replaced_count = max(0, params.end_line - params.start_line + 1)
        new_line_count = len(replacement.splitlines()) if replacement else 0
        return (
            f"Successfully edited '{params.repo_name}/{params.file_path}': "
            f"replaced lines {params.start_line}–{params.end_line} "
            f"({replaced_count} line(s) → {new_line_count} line(s))."
        )


class DevWriteFile(BaseSkill):
    name = "dev_write_file"
    description = (
        "Write the complete content of a file (creates new or overwrites existing). "
        "This is the primary way to modify files: read the file first with dev_read_file, "
        "then call this with the full updated content. "
        "Always supply the entire file — never partial content. "
        "IMPORTANT: do NOT include line numbers in the content. "
        "dev_read_file displays lines as '   42 | code here' for reference only — "
        "strip the line-number prefix before writing."
    )
    input_model = DevWriteFileInput

    def execute(self, params: DevWriteFileInput) -> str:
        try:
            full_path = _file_path(params.repo_name, params.file_path)
        except ValueError as e:
            return f"Error: {e}"

        import re as _re
        _line_num_prefix = _re.compile(r"^\s*\d+\s\|\s?")
        cleaned_lines = [
            _line_num_prefix.sub("", line) if _line_num_prefix.match(line) else line
            for line in params.content.splitlines(keepends=True)
        ]
        content = "".join(cleaned_lines)

        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content, encoding="utf-8")
        except Exception as e:
            return f"Error writing file: {e}"

        action = "Created" if not full_path.exists() else "Wrote"
        return f"{action} '{params.repo_name}/{params.file_path}' ({len(content.splitlines())} lines)."


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
