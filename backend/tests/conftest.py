"""Shared fixtures: throwaway git repositories built with subprocess git."""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        timeout=30,
    )


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "fixture-repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.name", "Alice")
    _git(repo, "config", "user.email", "alice@example.com")
    (repo / "f.txt").write_text("1\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1 on main")
    return repo


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    return make_repo(tmp_path)


@pytest.fixture
def repo_with_merge(tmp_path: Path) -> Path:
    """main: c1 --- c3 --- c4(merge of feature) / feature: c2 from c1."""
    repo = make_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    (repo / "f.txt").write_text("2\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c2 on feature")
    _git(repo, "checkout", "-q", "main")
    (repo / "g.txt").write_text("3\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c3 on main")
    _git(repo, "merge", "-q", "--no-ff", "-m", "c4 merge feature", "feature")
    return repo


@pytest.fixture
def repo_with_long_branch(tmp_path: Path) -> Path:
    """main: c1, m2, m3, c5(merge) / feature: 3 commits from c1."""
    repo = make_repo(tmp_path)
    _git(repo, "checkout", "-q", "-b", "feature")
    for i in range(2, 5):
        (repo / f"f{i}.txt").write_text(f"{i}\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", f"c{i} on feature")
    _git(repo, "checkout", "-q", "main")
    for i in (2, 3):
        (repo / f"m{i}.txt").write_text(f"{i}\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", f"c{i} on main")
    _git(repo, "merge", "-q", "--no-ff", "-m", "c5 merge feature", "feature")
    return repo
