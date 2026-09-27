"""Cross-repo tag search: list all repositories under a root that carry a
given tag name, with the tag's sha and (annotated) tagger date.

The endpoint is read-only and bounded: scan a tree of `.git` directories,
read each repo's tags in a single `git for-each-ref` call, and filter on
the name. Both the scan and per-repo git calls respect the same time
budget as the existing `/repos/browse`, so a misconfigured root cannot
stall the API.
"""
from __future__ import annotations

import logging
import os
import time

from fastapi import APIRouter, HTTPException, Query

from ..models.tags import TagHit, TagsFindResponse
from ..services import git_reader, scan

log = logging.getLogger("gitlane.tags")

router = APIRouter(tags=["tags"])

TAG_FIND_BUDGET_SECONDS = 10.0
DEFAULT_TAG_FIND_DEPTH = 2


def _validate_tag_name(tag: str) -> str:
    """Sanitize a tag name passed by the user.

    Git ref names forbid a small set of characters (`:`, `~`, `^`, `?`, `*`,
    `[`, backslash, spaces, .., leading `-`, `@{`) and must not be `.` or
    `..`. We reject anything that wouldn't survive `git check-ref-format`
    rather than try to escape it — a tag with `..` is a mistake, not a request.
    """
    if not tag or len(tag) > 200:
        raise HTTPException(status_code=400, detail="tag name must be 1-200 chars")
    if tag in (".", "..") or tag.startswith("-") or tag.endswith(".lock") or "@{" in tag:
        raise HTTPException(status_code=400, detail="invalid tag name")
    forbidden = set(' :~^?*[\\')
    if any(ch in forbidden for ch in tag):
        raise HTTPException(status_code=400, detail="tag name contains forbidden characters")
    return tag


def _age_seconds(ts: int) -> int:
    if not ts:
        return 0
    return max(0, int(time.time()) - ts)


@router.get("/tags/find", response_model=TagsFindResponse)
def tags_find(
    root: str = Query(..., min_length=1, max_length=1024, description="absolute root directory to scan"),
    tag: str = Query(..., min_length=1, max_length=200, description="exact tag name to look up"),
    depth: int = Query(DEFAULT_TAG_FIND_DEPTH, ge=1, le=scan.MAX_DEPTH),
) -> TagsFindResponse:
    """List every repo under `root` whose tags include `tag`."""
    tag = _validate_tag_name(tag)

    if not os.path.isdir(root):
        raise HTTPException(status_code=400, detail="root is not a directory")
    abs_root = os.path.abspath(root)
    if scan.is_refused_root(abs_root):
        raise HTTPException(status_code=400, detail="scanning system directories is not allowed")

    deadline = time.monotonic() + TAG_FIND_BUDGET_SECONDS
    found, complete = scan.scan(abs_root, depth, deadline=deadline)
    truncated = not complete or len(found) >= scan.MAX_RESULTS

    items: list[TagHit] = []
    missing: list[str] = []
    for repo in found[:scan.MAX_RESULTS]:
        if time.monotonic() > deadline:
            truncated = True
            break
        path = repo["path"]
        try:
            tags = git_reader.read_tags_with_dates(path)
        except git_reader.GitError as exc:
            log.info("read_tags_with_dates(%s) failed: %s", path, exc)
            missing.append(path)
            continue
        hit = tags.get(tag)
        if not hit:
            continue
        sha, ts = hit
        items.append(TagHit(
            repo_name=repo["name"],
            repo_path=path,
            tag_name=tag,
            sha=sha,
            age_seconds=_age_seconds(ts),
        ))

    items.sort(key=lambda h: (-h.age_seconds, h.repo_name.lower()))

    return TagsFindResponse(
        root=root,
        tag=tag,
        scanned=len(found[:scan.MAX_RESULTS]),
        truncated=truncated,
        items=items,
        missing=missing,
    )