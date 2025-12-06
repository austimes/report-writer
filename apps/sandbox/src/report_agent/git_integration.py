"""Git integration for report-agent CLI.

Provides MANDATORY git integration for report projects. Every report project
must be its own git repository with a .report-agent.json metadata file.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPORT_META_FILENAME = ".report-agent.json"
GITHUB_ORG = "austimes"


def require_executable(name: str) -> None:
    """Check if executable exists on PATH, raise RuntimeError if not."""
    if shutil.which(name) is None:
        raise RuntimeError(
            f"Required executable '{name}' not found on PATH. "
            f"Please install {name} and ensure it is available."
        )


def run_git(args: list[str], cwd: Path, desc: str) -> str:
    """Run git command, return stdout. Raise RuntimeError with full stderr on failure."""
    require_executable("git")
    cmd = ["git"] + args
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"Git operation failed: {desc}\n"
            f"Command: {' '.join(cmd)}\n"
            f"Exit code: {e.returncode}\n"
            f"Stdout: {e.stdout}\n"
            f"Stderr: {e.stderr}"
        ) from e


def run_gh(args: list[str], cwd: Path, desc: str) -> str:
    """Run gh CLI command, return stdout. Raise RuntimeError with full stderr on failure."""
    require_executable("gh")
    cmd = ["gh"] + args
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"GitHub CLI operation failed: {desc}\n"
            f"Command: {' '.join(cmd)}\n"
            f"Exit code: {e.returncode}\n"
            f"Stdout: {e.stdout}\n"
            f"Stderr: {e.stderr}"
        ) from e


def load_report_meta(output_root: Path) -> dict:
    """Load and return .report-agent.json contents.
    
    Raises RuntimeError if file doesn't exist or is invalid JSON.
    """
    meta_path = output_root / REPORT_META_FILENAME
    if not meta_path.exists():
        raise RuntimeError(
            f"Report metadata file not found: {meta_path}\n"
            f"Run `report-agent init-report` first to initialize a report project."
        )
    
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Invalid JSON in {meta_path}: {e}\n"
            f"Please fix the JSON syntax or reinitialize the report project."
        ) from e


def ensure_report_project(output_root: Path) -> dict:
    """Validate that output_root is a valid report project.
    
    Validates:
    - output_root exists
    - output_root/.git exists (NOT parent discovery - each report is its own repo)
    - .report-agent.json exists and is valid
    
    Returns the metadata dict. Raises RuntimeError with helpful message if validation fails.
    """
    if not output_root.exists():
        raise RuntimeError(
            f"Report directory does not exist: {output_root}\n"
            f"Run `report-agent init-report` first to create a new report project."
        )
    
    if not output_root.is_dir():
        raise RuntimeError(
            f"Report path is not a directory: {output_root}\n"
            f"Please provide a valid directory path."
        )
    
    git_dir = output_root / ".git"
    if not git_dir.exists():
        raise RuntimeError(
            f"Not a git repository: {output_root}\n"
            f"Each report project must be its own git repository.\n"
            f"Run `report-agent init-report` first to initialize a report project."
        )
    
    return load_report_meta(output_root)


def auto_commit(output_root: Path, commit_message: str) -> None:
    """Stage ALL files, commit with message, and push to origin.
    
    Uses git add -A and --allow-empty for the commit.
    All steps must succeed or raise RuntimeError.
    """
    ensure_report_project(output_root)
    
    run_git(["add", "-A"], cwd=output_root, desc="staging all files")
    
    run_git(
        ["commit", "--allow-empty", "-m", commit_message],
        cwd=output_root,
        desc="committing changes",
    )
    
    run_git(["push", "origin", "main"], cwd=output_root, desc="pushing to origin")


def _slugify(name: str) -> str:
    """Convert a report name to a valid GitHub repo slug."""
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "report"


def init_repo(output_root: Path, report_name: str, private: bool = True) -> dict:
    """Initialize a new report repository.
    
    Steps:
    - Verify not inside another git repo (reject if parent has .git)
    - git init -b main
    - Create minimal .gitignore
    - Create .report-agent.json with metadata
    - Initial commit
    - Create GitHub repo via gh repo create
    - Push to origin
    
    Returns the metadata dict.
    """
    require_executable("git")
    require_executable("gh")
    
    output_root = output_root.resolve()
    
    if output_root.exists() and (output_root / ".git").exists():
        raise RuntimeError(
            f"Directory is already a git repository: {output_root}\n"
            f"Use a different directory or remove the existing .git folder."
        )
    
    parent = output_root.parent
    check_path = parent
    while check_path != check_path.parent:
        if (check_path / ".git").exists():
            raise RuntimeError(
                f"Cannot initialize report inside existing git repository.\n"
                f"Found .git at: {check_path}\n"
                f"Each report must be its own independent repository.\n"
                f"Please choose a directory outside of existing git repositories."
            )
        check_path = check_path.parent
    
    output_root.mkdir(parents=True, exist_ok=True)
    
    run_git(["init", "-b", "main"], cwd=output_root, desc="initializing repository")
    
    gitignore_content = """__pycache__/
*.pyc
.venv/
"""
    gitignore_path = output_root / ".gitignore"
    gitignore_path.write_text(gitignore_content, encoding="utf-8")
    
    slug = _slugify(report_name)
    repo_name = f"{GITHUB_ORG}/{slug}"
    
    metadata = {
        "report_name": report_name,
        "slug": slug,
        "github_repo": repo_name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "private": private,
    }
    
    meta_path = output_root / REPORT_META_FILENAME
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
        f.write("\n")
    
    run_git(["add", "-A"], cwd=output_root, desc="staging initial files")
    run_git(
        ["commit", "-m", f"Initial commit: {report_name}"],
        cwd=output_root,
        desc="creating initial commit",
    )
    
    visibility = "--private" if private else "--public"
    run_gh(
        ["repo", "create", repo_name, visibility, "--source", ".", "--push"],
        cwd=output_root,
        desc=f"creating GitHub repository {repo_name}",
    )
    
    return metadata
