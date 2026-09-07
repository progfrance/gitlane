"""Git data extraction through the git CLI (subprocess, no shell injection).

All commands run with a timeout and a fixed argument list — no user-controlled
shell strings are ever composed (see PLAN.md section 16).
"""
from __future__ import annotations

import os
import re
import subprocess
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum

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


class RemoteStatus(Enum):
    """Outcome of a remote-URL probe: missing / unparseable / ok."""
    NO_ORIGIN = "no_origin"
    UNPARSEABLE = "unparseable"
    OK = "ok"


def read_remote(repo_path: str) -> tuple[RemoteStatus, str | None]:
    """Return (status, url) for the repo's `origin` remote.

    Distinguishes three outcomes so the caller (or the API) can surface
    them separately:
      - NO_ORIGIN    : no `remote.origin.url` configured (or value empty).
      - UNPARSEABLE  : an origin is set but its URL does not match any
                       supported scheme (http(s), ssh://, git@host:path).
                       Surfaces as a 4xx in the API so the user notices.
      - OK + url     : the safe https URL to link from the UI.

    The returned URL is always `https://` with credentials stripped:
      https://token@host/org/repo.git -> https://host/org/repo
      git@host:org/sub/repo.git       -> https://host/org/sub/repo
    """
    import re
    from urllib.parse import urlsplit

    try:
        url = _run(repo_path, ["config", "--get", "remote.origin.url"], timeout=5).strip()
    except GitError:
        return (RemoteStatus.NO_ORIGIN, None)
    if not url:
        return (RemoteStatus.NO_ORIGIN, None)

    def _strip_git_suffix(path: str) -> str:
        p = path.strip().strip("/")
        if p.endswith(".git"):
            p = p[:-4]
        return p.strip("/")

    # http(s)/ssh URL forms: keep full repo path (supports nested groups).
    # `startswith` is a fast filter, but `urlsplit` accepts any scheme
    # (ftp, git, file, ...) — we must re-check `scheme` so a non-web URL
    # never slips through as an OK `https://` rewrite.
    if url.startswith("http://") or url.startswith("https://") or url.startswith("ssh://"):
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https", "ssh"):
            return (RemoteStatus.UNPARSEABLE, None)
        host = parsed.hostname
        if not host:
            return (RemoteStatus.UNPARSEABLE, None)
        host_port = f"{host}:{parsed.port}" if parsed.port else host
        repo_path = _strip_git_suffix(parsed.path)
        if not repo_path:
            return (RemoteStatus.UNPARSEABLE, None)
        return (RemoteStatus.OK, f"https://{host_port}/{repo_path}")

    # SCP-like syntax: git@host:group/subgroup/repo.git. Must be a single
    # colon (no scheme prefix) and the host cannot contain `/`.
    if "://" not in url:
        m = re.match(r"(?:[^@\s]+@)?([^@\s/:]+):(.+)$", url)
        if m:
            host = m.group(1)
            repo_path = _strip_git_suffix(m.group(2))
            if host and repo_path:
                return (RemoteStatus.OK, f"https://{host}/{repo_path}")

    return (RemoteStatus.UNPARSEABLE, None)


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


# LRU cache for commit-detail reads: keyboard navigation (j/k) re-selects
# neighbours and the drawer keeps re-rendering, so 1 git call per open
# becomes many per second. 200 entries covers the visible viewport and a
# generous ring of recent selections.
_DETAIL_CACHE_SIZE = 200
_detail_cache: "OrderedDict[str, CommitDetailData]" = OrderedDict()
_detail_lock = threading.Lock()


def read_commit_detail(repo_path: str, sha: str) -> CommitDetailData:
    """Read full detail for one commit: message, parents, files, stats.

    `sha` must be a hex prefix (4-40 chars); anything else is rejected as
    InvalidRefError (400-class) before touching git.

    Results are cached server-side keyed by `path:sha` (LRU) so the drawer's
    keyboard nav (j/k) does not re-run `git show` on every step. Cache is
    intentionally process-local — git data changes invalidate implicitly
    when the user reloads the repo via the watcher.
    """
    if not _SHA_ARG_RE.match(sha or ""):
        raise InvalidRefError(f"invalid sha: {sha!r}")
    key = f"{repo_path}\x00{sha}"
    with _detail_lock:
        cached = _detail_cache.get(key)
        if cached is not None:
            _detail_cache.move_to_end(key)
            return cached
    if not _is_valid_ref(sha):
        raise InvalidRefError(f"invalid sha: {sha!r}")

    # One `git show` call with both `--raw` and `--numstat`: unlike
    # `--name-status` (a mutually exclusive diff flag that would swallow
    # `--numstat`), `--raw` is a separate output mode and coexists with it,
    # so the output carries raw status lines plus numstat add/del triples.
    # `--first-parent` keeps merges well-defined: the drawer shows what the
    # merge brought in versus its first parent (raw and numstat agree there;
    # without it `--raw` emits nothing on merges while `--numstat` emits a
    # combined diff, leaving the file list empty).
    try:
        out = _run(
            repo_path,
            [
                "show",
                "--raw",
                "--numstat",
                "--no-renames",
                "--first-parent",
                "--format=%H%x1f%P%x1f%an%x1f%ae%x1f%at%x1f%s%x1f%b%x1e",
                sha,
            ],
            timeout=10,
        )
    except GitError as exc:
        msg = str(exc).lower()
        if "unknown revision" in msg or "bad revision" in msg or "ambiguous argument" in msg:
            raise InvalidRefError(f"unknown commit: {sha!r}") from exc
        raise

    header, _, body_out = out.partition("\x1e")
    parts = header.split("\x1f")
    if len(parts) < 7 or not parts[0].strip():
        raise InvalidRefError(f"unknown commit: {sha!r}")
    full_sha, parents, an, ae, at, subject, body = (parts + [""] * 7)[:7]

    # Parse the body section: `--raw` lines carry the file status, `--numstat`
    # lines the add/del counts. `--no-renames` (fixed argv above) makes both
    # sections name the same plain path, so the join key matches directly —
    # no `old => new` / brace-collapse handling needed.
    files: list[dict] = []
    per_file: dict[str, list[int]] = {}
    total_adds = 0
    total_dels = 0
    if body_out:
        for line in body_out.splitlines():
            tabs = line.split("\t")
            if tabs and tabs[0].startswith(":"):
                # raw row: ":<oldmode> <newmode> <oldsha> <newsha> <CODE>\t<path>"
                info, _, path = line.partition("\t")
                code = info.rsplit(" ", 1)[-1].strip()
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
                path = path.strip()
                if path:
                    files.append({"path": path, "status": status})
            elif len(tabs) == 3 and tabs[0].isdigit() and tabs[1].isdigit():
                # numstat row: "<adds>\t<dels>\t<path>"
                adds, dels = int(tabs[0]), int(tabs[1])
                path = tabs[2].strip()
                per_file[path] = [adds, dels]
                total_adds += adds
                total_dels += dels

    for f in files:
        if f["path"] in per_file:
            f["additions"] = per_file[f["path"]][0]
            f["deletions"] = per_file[f["path"]][1]

    data = CommitDetailData(
        sha=full_sha.strip(),
        subject=subject,
        body=body.strip(),
        author_name=an,
        author_email=ae,
        timestamp=int(at) if at.isdigit() else 0,
        parents=parents.split() if parents else [],
        additions=total_adds,
        deletions=total_dels,
        files=files,
    )
    with _detail_lock:
        _detail_cache[key] = data
        _detail_cache.move_to_end(key)
        while len(_detail_cache) > _DETAIL_CACHE_SIZE:
            _detail_cache.popitem(last=False)
    return data


def clear_detail_cache() -> None:
    """Drop the detail cache (used by tests; the watcher does not need it)."""
    with _detail_lock:
        _detail_cache.clear()
