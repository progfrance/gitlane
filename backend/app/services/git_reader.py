"""Git data extraction through the git CLI (subprocess, no shell injection).

All commands run with a timeout and a fixed argument list — no user-controlled
shell strings are ever composed (see PLAN.md section 16).
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field

GIT_TIMEOUT = 15  # seconds

_LOG_FORMAT = "%H%x1f%P%x1f%an%x1f%ae%x1f%at%x1f%s%x1f%D%x1e"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA_ARG_RE = re.compile(r"^[0-9a-f]{4,40}$")


class GitError(Exception):
    """Raised when a git command fails or the target is not a repository."""


class InvalidRefError(GitError):
    """Raised when a caller-supplied revision is not a safe ref token.

    Unlike other git failures this is a 400-class client error: callers must
    surface it instead of silently falling back to HEAD.
    """


class RepoNotFoundError(GitError):
    """Raised when the repository path vanished (404-class, not a 500)."""


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
        # One call for both: `rev-parse` accepts several expressions and
        # prints one result per line (sha, then branch or "HEAD" if detached).
        out = _run(repo_path, ["rev-parse", "HEAD", "--abbrev-ref", "HEAD"], timeout=5)
        lines = out.splitlines()
        data.head_sha = lines[0].strip() or None if lines else None
        data.head = lines[1].strip() if len(lines) > 1 and lines[1].strip() else "HEAD"
    except GitError:
        # Empty repo (no commits yet): no HEAD sha, keep a sensible branch name.
        data.head_sha = None
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
) -> list[CommitData]:
    """Read the full history of `ref` in topological order (children first).

    Diff stats are intentionally NOT loaded here — callers fetch them lazily
    per served page via read_diff_stats_for_shas (one `git log --numstat`
    over the whole history per open would double the git cost upfront).
    """
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

    return commits


def read_diff_stats_for_shas(
    repo_path: str, shas: list[str],
) -> dict[str, tuple[int, int]]:
    """Fetch additions/deletions for an explicit list of commits.

    Uses a single `git diff-tree --numstat --stdin` call so paginated views
    only pay for the rows actually served — no second full `git log` walk.
    Unknown SHAs are reported as (0, 0); callers fall back gracefully.
    """
    valid = [s for s in dict.fromkeys(shas) if _SHA_ARG_RE.match(s)]
    if not valid:
        return {}
    try:
        proc = subprocess.run(
            ["git", "-C", repo_path, "diff-tree", "--numstat", "--no-renames",
             "--format=%H", "--stdin"],
            input=("\n".join(valid) + "\n").encode(),
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
    cur: str | None = None
    acc: dict[str, list[int]] = {}
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if _SHA_RE.match(line):
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
    # Defensive: only allow ref-looking tokens — never options, whitespace,
    # control chars, or git revision operators that could escape the intent.
    if not ref or ref.startswith("-"):
        return False
    if any(c.isspace() or ord(c) < 32 for c in ref):
        return False
    if "\x00" in ref:
        return False
    if ref.startswith("+"):
        return False
    if any(op in ref for op in ("..", "@{", ":", "?", "*", "[", "\\", "^", "~")):
        return False
    return True


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
    try:
        return int(out.strip() or 0)
    except ValueError as exc:
        raise GitError(f"unexpected rev-list output: {out.strip()!r}") from exc


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


@dataclass
class CommitDetailData:
    sha: str
    subject: str = ""
    body: str = ""
    author_name: str = ""
    author_email: str = ""
    timestamp: int = 0
    parents: list[str] = field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    files: list[dict] = field(default_factory=list)


def _parse_name_status(out: str) -> list[dict]:
    """Parse `git show --name-status --format=` output into file entries."""
    files: list[dict] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        code, rest = parts[0], parts[1:]
        letter = code[:1].upper()
        if letter == "A":
            status = "added"
        elif letter == "D":
            status = "deleted"
        elif letter == "R":
            status = "renamed"
        elif letter == "M":
            status = "modified"
        else:
            status = "other"
        # Rename format: R100\told\tnew — display the new path.
        path = rest[-1] if rest else ""
        if path:
            files.append({"path": path, "status": status})
    return files


def read_commit_detail(repo_path: str, sha: str) -> CommitDetailData:
    """Read full detail for one commit: message, parents, files, stats.

    `sha` must be a hex prefix (4-40 chars); anything else is rejected as
    InvalidRefError (400-class) before touching git.
    """
    if not _SHA_ARG_RE.match(sha or ""):
        raise InvalidRefError(f"invalid sha: {sha!r}")
    try:
        header = _run(
            repo_path,
            ["show", "--no-patch", "--format=%H%x1f%P%x1f%an%x1f%ae%x1f%at%x1f%s%x1f%b%x1e", sha],
            timeout=10,
        )
    except GitError as exc:
        msg = str(exc).lower()
        if "unknown revision" in msg or "bad revision" in msg or "ambiguous argument" in msg:
            raise InvalidRefError(f"unknown commit: {sha!r}") from exc
        raise
    parts = header.split("\x1e")[0].split("\x1f")
    if len(parts) < 7 or not parts[0].strip():
        raise InvalidRefError(f"unknown commit: {sha!r}")
    full_sha, parents, an, ae, at, subject, body = (parts + [""] * 7)[:7]
    try:
        files_out = _run(repo_path, ["show", "--name-status", "--format=", sha], timeout=10)
    except GitError:
        files_out = ""
    stats = read_diff_stats_for_shas(repo_path, [full_sha.strip()])
    adds, dels = stats.get(full_sha.strip(), (0, 0))
    files = _parse_name_status(files_out)
    # Attach per-file stats for the common case (single numstat line per path).
    try:
        numstat = _run(repo_path, ["show", "--numstat", "--format=", sha], timeout=10)
        per_file: dict[str, list[int]] = {}
        for line in numstat.splitlines():
            bits = line.split("\t")
            if len(bits) >= 3 and bits[0].isdigit() and bits[1].isdigit():
                per_file[bits[2]] = [int(bits[0]), int(bits[1])]
        for f in files:
            if f["path"] in per_file:
                f["additions"], f["deletions"] = per_file[f["path"]]
    except GitError:
        pass
    return CommitDetailData(
        sha=full_sha.strip(),
        subject=subject,
        body=body.strip(),
        author_name=an,
        author_email=ae,
        timestamp=int(at) if at.isdigit() else 0,
        parents=parents.split() if parents else [],
        additions=adds,
        deletions=dels,
        files=files,
    )
