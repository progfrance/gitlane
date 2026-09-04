"""Git data extraction through the git CLI (subprocess, no shell injection).

All commands run with a timeout and a fixed argument list — no user-controlled
shell strings are ever composed (see PLAN.md section 16).
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field

GIT_TIMEOUT = 15  # seconds

_LOG_FORMAT = "%H%x1f%P%x1f%an%x1f%ae%x1f%at%x1f%s%x1f%D%x1e"


class GitError(Exception):
    """Raised when a git command fails or the target is not a repository."""


class InvalidRefError(GitError):
    """Raised when a caller-supplied revision is not a safe ref token.

    Unlike other git failures this is a 400-class client error: callers must
    surface it instead of silently falling back to HEAD.
    """


@dataclass
class CommitData:
    sha: str
    parents: list[str] = field(default_factory=list)
    author_name: str = ""
    author_email: str = ""
    timestamp: int = 0
    subject: str = ""
    decorations: list[str] = field(default_factory=list)
    additions: int = 0
    deletions: int = 0


@dataclass
class RefsData:
    head: str = "HEAD"
    head_sha: str | None = None
    local_branches: dict[str, str] = field(default_factory=dict)   # shortname -> sha
    remote_branches: dict[str, str] = field(default_factory=dict)  # shortname -> sha
    tags: dict[str, str] = field(default_factory=dict)             # shortname -> sha


def _run(repo_path: str, args: list[str], timeout: int = GIT_TIMEOUT) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", repo_path, *args],
            capture_output=True,
            timeout=timeout,
            check=True,
        )
    except FileNotFoundError as exc:
        raise GitError("git executable not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError(f"git {' '.join(args[:2])} timed out") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode(errors="replace").strip() if exc.stderr else ""
        raise GitError(stderr or f"git {' '.join(args[:2])} failed") from exc
    return proc.stdout.decode(errors="replace")


def is_git_repo(path: str) -> bool:
    if not path or not os.path.isdir(path):
        return False
    try:
        out = _run(path, ["rev-parse", "--show-toplevel"], timeout=5)
    except GitError:
        return False
    # The discovered work tree must be the directory itself, not a parent
    # repo that merely contains it.
    toplevel = os.path.normpath(out.strip())
    return toplevel == os.path.normpath(os.path.abspath(path))


def repo_name(path: str) -> str:
    return os.path.basename(os.path.normpath(path)) or path


def read_refs(repo_path: str) -> RefsData:
    data = RefsData()
    try:
        data.head_sha = _run(repo_path, ["rev-parse", "HEAD"]).strip() or None
    except GitError:
        # Empty repo (no commits yet): no HEAD sha, keep a sensible branch name.
        data.head_sha = None
    try:
        data.head = _run(repo_path, ["rev-parse", "--abbrev-ref", "HEAD"]).strip() or "HEAD"
    except GitError:
        data.head = "HEAD"

    for_each = _run(
        repo_path,
        ["for-each-ref", "--format=%(refname)%00%(objectname)", "refs/"],
    )
    for line in for_each.splitlines():
        if not line or "\x00" not in line:
            continue
        refname, sha = line.split("\x00", 1)
        if refname.startswith("refs/heads/"):
            data.local_branches[refname[len("refs/heads/"):]] = sha
        elif refname.startswith("refs/remotes/") and not refname.endswith("/HEAD"):
            data.remote_branches[refname[len("refs/remotes/"):]] = sha
        elif refname.startswith("refs/tags/"):
            data.tags[refname[len("refs/tags/"):]] = sha
    return data


def read_commits(
    repo_path: str, ref: str = "HEAD", max_count: int | None = None,
    with_stats: bool = False,
) -> list[CommitData]:
    """Read the full history of `ref` in topological order (children first)."""
    args = ["log", "--topo-order", f"--format={_LOG_FORMAT}"]
    if max_count:
        args.append(f"--max-count={max_count}")
    # Revision must come BEFORE the "--" separator, otherwise git treats it
    # as a path spec and returns an empty log.
    args.append(resolve_rev(ref))
    args.append("--")

    try:
        out = _run(repo_path, args)
    except GitError as exc:
        msg = str(exc).lower()
        if "unknown revision" in msg or "bad revision" in msg:
            # Ambiguous git message: "bad revision 'HEAD'" also means the
            # repo simply has no commits yet — treat that as empty history.
            if ref in ("HEAD", "") and not has_commits(repo_path):
                return []
            raise InvalidRefError(f"unknown ref: {ref!r}") from exc
        if "does not have any commits yet" in msg or "bad default revision" in msg:
            # Empty repo (no commits yet on this ref): return no commits.
            return []
        raise
    commits: list[CommitData] = []
    for record in out.split("\x1e"):
        record = record.strip("\n")
        if not record.strip():
            continue
        parts = record.split("\x1f")
        if len(parts) < 7:
            continue
        sha, parents, an, ae, at, subject, deco = parts[:7]
        decorations = []
        for d in deco.split(","):
            d = d.strip()
            if d and d not in ("HEAD", "grafted", "staged-changes", "staged-contents"):
                decorations.append(d)
        commits.append(
            CommitData(
                sha=sha,
                parents=parents.split() if parents else [],
                author_name=an,
                author_email=ae,
                timestamp=int(at) if at.isdigit() else 0,
                subject=subject,
                decorations=decorations,
            )
        )

    if with_stats and commits:
        stats = _read_diff_stats(repo_path, ref, max_count)
        for c in commits:
            a, d = stats.get(c.sha, (0, 0))
            c.additions, c.deletions = a, d

    return commits


def _read_diff_stats(
    repo_path: str, ref: str, max_count: int | None,
) -> dict[str, tuple[int, int]]:
    """Fetch per-commit line additions/deletions via --numstat."""
    args = ["log", "--numstat", "--format=%H"]
    if max_count:
        args.append(f"--max-count={max_count}")
    args.append(resolve_rev(ref))
    args.append("--")
    out = _run(repo_path, args)
    return _parse_numstat(out)


def read_diff_stats_for_shas(
    repo_path: str, shas: list[str],
) -> dict[str, tuple[int, int]]:
    """Fetch additions/deletions for an explicit list of commits.

    Uses a single `git diff-tree --numstat --stdin` call so paginated views
    only pay for the rows actually served — no second full `git log` walk.
    Unknown SHAs are reported as (0, 0); callers fall back gracefully.
    """
    if not shas:
        return {}
    try:
        proc = subprocess.run(
            ["git", "-C", repo_path, "diff-tree", "--numstat", "--no-renames",
             "--format=%H", "--stdin"],
            input=("\n".join(shas) + "\n").encode(),
            capture_output=True,
            timeout=GIT_TIMEOUT,
            check=True,
        )
    except FileNotFoundError as exc:
        raise GitError("git executable not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise GitError("git diff-tree timed out") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode(errors="replace").strip() if exc.stderr else ""
        raise GitError(stderr or "git diff-tree failed") from exc
    return _parse_numstat(proc.stdout.decode(errors="replace"))


def _parse_numstat(out: str) -> dict[str, tuple[int, int]]:
    """Parse `--numstat` output (SHA lines + add/del/file triples)."""
    import re

    SHA_RE = re.compile(r"^[0-9a-f]{40}$")
    cur: str | None = None
    acc: dict[str, list[int]] = {}
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if SHA_RE.match(line):
            cur = line
            if cur not in acc:
                acc[cur] = [0, 0]
            continue
        if cur is None:
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            adds, dels = parts[0], parts[1]
            if adds.isdigit() and dels.isdigit():
                acc[cur][0] += int(adds)
                acc[cur][1] += int(dels)
    return {sha: (a, d) for sha, (a, d) in acc.items()}


def has_commits(repo_path: str) -> bool:
    """True when the repo has at least one commit (HEAD resolves)."""
    try:
        _run(repo_path, ["rev-parse", "--verify", "--quiet", "HEAD"], timeout=5)
    except GitError:
        return False
    return True


def _is_valid_ref(ref: str) -> bool:
    # Defensive: only allow ref-looking tokens, never options.
    return bool(ref) and not ref.startswith("-") and " " not in ref and "\x00" not in ref


def resolve_rev(ref: str) -> str:
    """Return `ref` when safe, else raise InvalidRefError (400-class).

    Previous behaviour silently fell back to HEAD, hiding caller bugs
    (e.g. a typo'd branch name rendering the wrong history).
    """
    if _is_valid_ref(ref):
        return ref
    raise InvalidRefError(f"invalid ref: {ref!r}")


def count_commits(repo_path: str, ref: str = "HEAD") -> int:
    try:
        out = _run(repo_path, ["rev-list", "--count", resolve_rev(ref)])
    except GitError:
        # Empty repo (no HEAD yet) reports 0 instead of erroring.
        return 0
    return int(out.strip() or 0)


def _sanitize_rev(ref: str) -> str:
    # Kept for backward compatibility; prefer resolve_rev for request paths.
    return ref if _is_valid_ref(ref) else "HEAD"


def relative_time(timestamp: int, now: int | None = None) -> str:
    """Human readable relative time (English, as per the visual spec)."""
    import time

    now = now if now is not None else int(time.time())
    delta = max(0, now - timestamp)
    if delta < 60:
        return "just now"
    minutes = delta // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = hours // 24
    if days < 31:
        return f"{days} day{'s' if days != 1 else ''} ago"
    months = days // 31
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''} ago"
    years = days // 365
    return f"{years} year{'s' if years != 1 else ''} ago"


def read_remote(repo_path: str) -> str | None:
    """Return a safe web URL base for the repo's origin remote.

    Supports GitHub/GitLab/Bitbucket/Azure-style remotes and strips
    credentials if present:
      https://token@host/org/repo.git -> https://host/org/repo
      git@host:org/repo.git           -> https://host/org/repo
      ssh://git@host/org/repo.git     -> https://host/org/repo
    Returns None when no origin remote is configured or parsing fails.
    """
    import re
    from urllib.parse import urlsplit

    try:
        url = _run(repo_path, ["config", "--get", "remote.origin.url"], timeout=5).strip()
    except GitError:
        return None
    if not url:
        return None

    def _strip_git_suffix(path: str) -> str:
        p = path.strip().strip("/")
        if p.endswith(".git"):
            p = p[:-4]
        return p.strip("/")

    # http(s)/ssh URL forms: keep full repo path (supports nested groups).
    if url.startswith("http://") or url.startswith("https://") or url.startswith("ssh://"):
        parsed = urlsplit(url)
        host = parsed.hostname
        if not host:
            return None
        host_port = f"{host}:{parsed.port}" if parsed.port else host
        repo_path = _strip_git_suffix(parsed.path)
        if not repo_path:
            return None
        return f"https://{host_port}/{repo_path}"

    # SCP-like syntax: git@host:group/subgroup/repo.git
    m = re.match(r"(?:[^@\s]+@)?([^:\s]+):(.+)$", url)
    if m:
        host = m.group(1)
        repo_path = _strip_git_suffix(m.group(2))
        if host and repo_path:
            return f"https://{host}/{repo_path}"

    return None
