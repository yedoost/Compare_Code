from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Optional


class GitError(RuntimeError):
    pass


def _run_git(args: list[str], cwd: Optional[Path] = None) -> None:
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise GitError(result.stderr.strip() or result.stdout.strip())


def _hash_repo(repo: str) -> str:
    return hashlib.sha256(repo.encode("utf-8")).hexdigest()[:12]


def checkout_git_source(repo: str, ref: str, cache_dir: Path) -> Path:
    repos_dir = cache_dir / "repos"
    worktrees_dir = cache_dir / "worktrees"
    repos_dir.mkdir(parents=True, exist_ok=True)
    worktrees_dir.mkdir(parents=True, exist_ok=True)
    repo_key = _hash_repo(repo)
    repo_dir = repos_dir / repo_key
    if not repo_dir.exists():
        _run_git(["clone", "--mirror", repo, str(repo_dir)])
    else:
        _run_git(["fetch", "--all", "--tags"], cwd=repo_dir)
    worktree_dir = worktrees_dir / repo_key / ref
    if not worktree_dir.exists():
        worktree_dir.parent.mkdir(parents=True, exist_ok=True)
        _run_git(["worktree", "add", "-f", str(worktree_dir), ref], cwd=repo_dir)
    return worktree_dir
