"""API contract tests: run the FastAPI app against a fixture repo."""
from __future__ import annotations

import warnings

import pytest

warnings.filterwarnings("ignore", category=DeprecationWarning)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.cache import cache  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def opened(client, repo_with_merge):
    cache.invalidate(str(repo_with_merge))
    r = client.post("/repos/open", json={"path": str(repo_with_merge)})
    assert r.status_code == 200, r.text
    return str(repo_with_merge)


class TestOpenRepo:
    def test_open_ok(self, client, git_repo):
        r = client.post("/repos/open", json={"path": str(git_repo)})
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["repo"]["name"] == git_repo.name
        assert body["repo"]["commit_count"] >= 1

    def test_open_exposes_remote_url(self, client, git_repo):
        # A repo without a GitHub origin gets remote=None (not an error).
        r = client.post("/repos/open", json={"path": str(git_repo)})
        assert r.status_code == 200
        assert "remote" in r.json()["repo"]
        assert r.json()["repo"]["remote"] is None

    def test_open_rejects_missing_dir(self, client, tmp_path):
        r = client.post("/repos/open", json={"path": str(tmp_path / "nope")})
        assert r.status_code == 400

    def test_open_rejects_relative_path(self, client):
        r = client.post("/repos/open", json={"path": "relative/path"})
        assert r.status_code == 400

    def test_open_rejects_non_repo(self, client, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        r = client.post("/repos/open", json={"path": str(plain)})
        assert r.status_code == 400


class TestHistory:
    def test_history_contract(self, opened, client):
        r = client.get("/history", params={"path": opened, "limit": 2})
        assert r.status_code == 200
        body = r.json()
        assert set(body) >= {"items", "next_cursor", "has_more", "total", "max_lane"}
        for item in body["items"]:
            assert set(item) >= {
                "sha", "short_sha", "message_subject", "author_name",
                "author_email", "timestamp", "parents",
                "refs", "lane_index", "node", "segments",
                "additions", "deletions", "is_head",
            }
            assert "relative_time" not in item
            assert "status_checks" not in item
            assert "author_avatar_url" not in item
            node = item["node"]
            assert {"x", "y", "r", "color"} <= set(node)
            for seg in item["segments"]:
                assert {"type", "x1", "y1", "x2", "y2", "color", "w"} <= set(seg)

    def test_pagination(self, opened, client):
        r1 = client.get("/history", params={"path": opened, "limit": 2})
        b1 = r1.json()
        assert b1["has_more"] is True and b1["next_cursor"]
        r2 = client.get("/history", params={"path": opened, "limit": 2, "cursor": b1["next_cursor"]})
        b2 = r2.json()
        assert b2["items"]
        assert b1["items"][0]["sha"] != b2["items"][0]["sha"]

    def test_search_filters(self, opened, client):
        r = client.get("/history", params={"path": opened, "q": "feature"})
        body = r.json()
        assert body["total"] >= 1
        matched = [i for i in body["items"] if i["matched"]]
        assert matched
        assert all("feature" in i["message_subject"].lower() for i in matched)

    def test_search_includes_parents_as_context(self, opened, client):
        # "c2 on feature" is a child of c1: the search hit plus its parent
        # chain must be present so the lane graph stays connected.
        r = client.get("/history", params={"path": opened, "q": "c2 on feature", "limit": 50})
        body = r.json()
        assert body["total"] >= 2
        hits = [i for i in body["items"] if i["matched"]]
        context = [i for i in body["items"] if not i["matched"]]
        assert len(hits) == 1 and hits[0]["message_subject"] == "c2 on feature"
        assert context, "parents of the hit must be included as context"
        hit_parents = set(hits[0]["parents"])
        assert any(c["sha"] in hit_parents for c in context)

    def test_history_requires_open(self, client, tmp_path):
        r = client.get("/history", params={"path": str(tmp_path)})
        assert r.status_code == 404

    def test_history_reopens_evicted_repo(self, client, git_repo):
        # Regression: switching repos evicted the previous entry and an
        # in-flight /history call then failed with "repo not open". The
        # cache now self-heals by reloading a valid repo from disk.
        cache.invalidate(str(git_repo))
        r = client.get("/history", params={"path": str(git_repo)})
        assert r.status_code == 200
        assert r.json()["items"]


class TestRefs:
    def test_refs_lists_branches(self, opened, client):
        r = client.get("/refs", params={"path": opened})
        assert r.status_code == 200
        body = r.json()
        names = [b["name"] for b in body["local_branches"]]
        assert "main" in names and "feature" in names
        kinds = {b["kind"] for b in body["local_branches"]}
        assert kinds == {"local_branch"}

    def test_refs_refreshes_new_branch(self, client, repo_with_merge, tmp_path):
        import subprocess

        cache.invalidate(str(repo_with_merge))
        client.post("/repos/open", json={"path": str(repo_with_merge)})
        subprocess.run(
            ["git", "-C", str(repo_with_merge), "checkout", "-q", "-b", "fresh-branch"],
            check=True, capture_output=True, timeout=30,
        )
        r = client.get("/refs", params={"path": str(repo_with_merge)})
        names = [b["name"] for b in r.json()["local_branches"]]
        assert "fresh-branch" in names


class TestBranchSwitch:
    """The /history `ref` parameter must filter to the selected branch."""

    def test_history_defaults_to_head(self, opened, client):
        r = client.get("/history", params={"path": opened, "limit": 50})
        body = r.json()
        assert body["active_ref"] == "main"
        assert body["total"] == 4  # c1 c2(merged) c3 c4 — full main history

    def test_history_switches_branch(self, opened, client):
        r = client.get("/history", params={"path": opened, "ref": "feature", "limit": 50})
        assert r.status_code == 200
        body = r.json()
        assert body["active_ref"] == "feature"
        subjects = [i["message_subject"] for i in body["items"]]
        assert "c2 on feature" in subjects
        assert "c3 on main" not in subjects
        assert "c4 merge feature" not in subjects

    def test_history_ref_back_and_forth_uses_cache(self, opened, client):
        r1 = client.get("/history", params={"path": opened, "ref": "feature"})
        r2 = client.get("/history", params={"path": opened, "ref": "main"})
        r3 = client.get("/history", params={"path": opened, "ref": "feature"})
        assert r1.json()["total"] == 2
        assert r2.json()["total"] == 4
        assert r3.json()["total"] == 2
        assert r3.json()["active_ref"] == "feature"

    def test_history_is_head_follows_branch(self, opened, client):
        r = client.get("/history", params={"path": opened, "ref": "feature", "limit": 50})
        items = r.json()["items"]
        head = next(i for i in items if i["is_head"])
        assert head["message_subject"] == "c2 on feature"

    def test_history_unknown_ref_returns_400(self, opened, client):
        r = client.get("/history", params={"path": opened, "ref": "no-such-branch"})
        assert r.status_code == 400

    def test_timeline_honors_ref(self, opened, client):
        r = client.get("/timeline", params={"path": opened, "ref": "feature"})
        assert r.status_code == 200
        total = sum(p["count"] for p in r.json()["points"])
        assert total == 2


class TestLayoutInHistory:
    def test_merge_commit_has_merge_curve(self, opened, client):
        r = client.get("/history", params={"path": opened, "limit": 50})
        items = r.json()["items"]
        merge = next(i for i in items if "merge" in i["message_subject"])
        curves = [s for s in merge["segments"] if s["type"] == "curve"]
        assert curves, "merge commit must carry a curve segment"

    def test_lane_colors_valid(self, opened, client):
        r = client.get("/history", params={"path": opened, "limit": 50})
        palette = {
            "#d6409f", "#8e4ec6", "#0091ff", "#00a2c7", "#f5a623", "#30a46c",
            "#e5484d", "#6e56cf", "#12b5cb", "#e2b714", "#3eb8b3", "#7ee787",
        }
        for item in r.json()["items"]:
            assert item["node"]["color"] in palette
            for seg in item["segments"]:
                assert seg["color"] in palette


class TestGitReaderRemote:
    def test_read_remote_parses_github_urls(self, tmp_path, monkeypatch):
        from app.services import git_reader

        repo = tmp_path / "remote-repo"
        repo.mkdir()

        def fake_run(path, args, timeout=15):
            assert args[:2] == ["config", "--get"]
            return "git@github.com:progfrance/gitlane.git\n"

        monkeypatch.setattr(git_reader, "_run", fake_run)
        _status, _url = git_reader.read_remote(str(repo))
        assert _status == git_reader.RemoteStatus.OK
        assert _url == "https://github.com/progfrance/gitlane"

    def test_read_remote_https_and_git_suffix(self, tmp_path, monkeypatch):
        from app.services import git_reader

        repo = tmp_path / "remote-repo"
        repo.mkdir()
        monkeypatch.setattr(
            git_reader, "_run",
            lambda path, args, timeout=15: "https://github.com/owner/repo.git\n",
        )
        _status, _url = git_reader.read_remote(str(repo))
        assert _status == git_reader.RemoteStatus.OK
        assert _url == "https://github.com/owner/repo"

    def test_read_remote_non_github_supported(self, tmp_path, monkeypatch):
        from app.services import git_reader

        repo = tmp_path / "remote-repo"
        repo.mkdir()
        monkeypatch.setattr(
            git_reader, "_run",
            lambda path, args, timeout=15: "git@gitlab.com:owner/repo.git\n",
        )
        _status, _url = git_reader.read_remote(str(repo))
        assert _status == git_reader.RemoteStatus.OK
        assert _url == "https://gitlab.com/owner/repo"

    def test_read_remote_nested_groups(self, tmp_path, monkeypatch):
        from app.services import git_reader

        repo = tmp_path / "remote-repo"
        repo.mkdir()
        monkeypatch.setattr(
            git_reader, "_run",
            lambda path, args, timeout=15: "git@gitlab.com:group/subgroup/repo.git\n",
        )
        _status, _url = git_reader.read_remote(str(repo))
        assert _status == git_reader.RemoteStatus.OK
        assert _url == "https://gitlab.com/group/subgroup/repo"

    def test_read_remote_unparsable_is_none(self, tmp_path, monkeypatch):
        from app.services import git_reader

        repo = tmp_path / "remote-repo"
        repo.mkdir()
        monkeypatch.setattr(
            git_reader, "_run",
            lambda path, args, timeout=15: "not-a-valid-remote\n",
        )
        _status, _url = git_reader.read_remote(str(repo))
        assert _status == git_reader.RemoteStatus.UNPARSEABLE
        assert _url is None

    def test_read_remote_missing_remote_is_none(self, tmp_path, monkeypatch):
        from app.services import git_reader
        from app.services.git_reader import GitError

        repo = tmp_path / "remote-repo"
        repo.mkdir()
        monkeypatch.setattr(git_reader, "_run", lambda path, args, timeout=15: (_ for _ in ()).throw(GitError("no remote")))
        status, url = git_reader.read_remote(str(repo))
        assert status == git_reader.RemoteStatus.NO_ORIGIN
        assert url is None


class TestEvents:
    def test_websocket_connects(self, client):
        with client.websocket_connect("/events") as ws:
            # Session alive: a send must not raise (server keeps reading).
            ws.send_text("ping")
            assert ws.send_text("pong") is None


class TestLazyStats:
    """Diff stats are served per page (no full double git log on open)."""

    def test_history_serves_real_stats(self, opened, client):
        r = client.get("/history", params={"path": opened, "limit": 50})
        assert r.status_code == 200
        items = r.json()["items"]
        assert any(i["additions"] + i["deletions"] > 0 for i in items)

    def test_timeline_has_adds_dels(self, opened, client):
        r = client.get("/timeline", params={"path": opened})
        assert r.status_code == 200
        points = r.json()["points"]
        assert any("adds" in p and "dels" in p for p in points)
        assert sum(p["adds"] for p in points) + sum(p["dels"] for p in points) > 0

    def test_stats_cached_on_view(self, opened, client):
        from app.services.cache import cache
        from app.services import view_builder

        client.get("/history", params={"path": opened, "limit": 1})
        state = cache.require(opened)
        view = view_builder.get_view(state, opened, "HEAD")
        assert view.stats, "served page SHAs must be cached on the view"


class TestInvalidRef:
    def test_history_option_like_ref_returns_400(self, opened, client):
        r = client.get("/history", params={"path": opened, "ref": "--all"})
        assert r.status_code == 400

    def test_timeline_option_like_ref_returns_400(self, opened, client):
        r = client.get("/timeline", params={"path": opened, "ref": "--all"})
        assert r.status_code == 400


class TestEmptyRepo:
    def test_open_empty_repo_ok(self, client, tmp_path):
        import subprocess

        repo = tmp_path / "empty-repo"
        repo.mkdir()
        subprocess.run(
            ["git", "-C", str(repo), "init", "-q", "-b", "main"],
            check=True, capture_output=True, timeout=30,
        )
        r = client.post("/repos/open", json={"path": str(repo)})
        assert r.status_code == 200
        assert r.json()["repo"]["commit_count"] == 0

    def test_history_empty_repo_is_empty(self, client, tmp_path):
        import subprocess

        repo = tmp_path / "empty-repo"
        repo.mkdir()
        subprocess.run(
            ["git", "-C", str(repo), "init", "-q", "-b", "main"],
            check=True, capture_output=True, timeout=30,
        )
        client.post("/repos/open", json={"path": str(repo)})
        r = client.get("/history", params={"path": str(repo)})
        assert r.status_code == 200
        assert r.json()["total"] == 0
        assert r.json()["items"] == []


class TestCommitDetail:
    """GET /commit/detail returns message body, parents, files and stats."""

    def test_detail_contract(self, opened, client):
        sha = client.get("/history", params={"path": opened, "limit": 1}).json()["items"][0]["sha"]
        r = client.get("/commit/detail", params={"path": opened, "sha": sha})
        assert r.status_code == 200
        body = r.json()
        assert body["sha"] == sha
        assert body["short_sha"] == sha[:7]
        assert set(body) >= {
            "message_subject", "message_body", "author_name", "author_email",
            "timestamp", "parents", "refs", "additions", "deletions",
            "files", "is_head",
        }
        assert isinstance(body["files"], list)
        assert body["additions"] + body["deletions"] >= 0

    def test_detail_bad_sha_returns_400(self, opened, client):
        r = client.get("/commit/detail", params={"path": opened, "sha": "not-a-sha!!"})
        assert r.status_code == 400

    def test_detail_unknown_sha_returns_400(self, opened, client):
        r = client.get("/commit/detail", params={"path": opened, "sha": "deadbeef"})
        assert r.status_code == 400

    def test_detail_requires_open(self, client, tmp_path):
        r = client.get("/commit/detail", params={"path": str(tmp_path), "sha": "deadbeef"})
        assert r.status_code == 404

    def test_detail_stats_match_numstat(self, opened, client):
        """Regression: --name-status used to swallow --numstat (totals +0/-0).

        The reference command mirrors the implementation's flags exactly
        (--first-parent included): on merge commits the combined diff and
        the first-parent diff legitimately differ, so comparing against a
        plain `git show --numstat` would assert the wrong expectation.
        """
        import subprocess
        sha = client.get("/history", params={"path": opened, "limit": 1}).json()["items"][0]["sha"]
        numstat = subprocess.run(
            ["git", "-C", opened, "show", "--numstat", "--no-renames", "--first-parent", "--format=", sha],
            capture_output=True, text=True, timeout=30,
        ).stdout
        expect_adds = expect_dels = 0
        expect_files = 0
        for line in numstat.splitlines():
            tabs = line.split("\t")
            if len(tabs) == 3 and tabs[0].isdigit() and tabs[1].isdigit():
                expect_adds += int(tabs[0])
                expect_dels += int(tabs[1])
                expect_files += 1
        body = client.get("/commit/detail", params={"path": opened, "sha": sha}).json()
        assert body["additions"] == expect_adds
        assert body["deletions"] == expect_dels
        assert len(body["files"]) == expect_files
        if expect_files:
            per_file = {f["path"]: f for f in body["files"]}
            for line in numstat.splitlines():
                tabs = line.split("\t")
                if len(tabs) == 3 and tabs[0].isdigit() and tabs[1].isdigit():
                    f = per_file[tabs[2]]
                    assert f["additions"] == int(tabs[0])
                    assert f["deletions"] == int(tabs[1])


class TestRefsPagination:
    def test_refs_pagination(self, opened, client):
        r = client.get("/refs", params={"path": opened, "limit": 1, "offset": 0})
        assert r.status_code == 200
        assert len(r.json()["local_branches"]) == 1

    def test_refs_search(self, opened, client):
        r = client.get("/refs", params={"path": opened, "q": "main"})
        assert r.status_code == 200
        names = [b["name"] for b in r.json()["local_branches"]]
        assert names == ["main"]


class TestRecentValidation:
    def test_recent_rejects_non_repo(self, client, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        r = client.post("/repos/recent", json={"path": str(plain)})
        assert r.status_code == 400

    def test_recent_rejects_missing_dir(self, client, tmp_path):
        r = client.post("/repos/recent", json={"path": str(tmp_path / "nope")})
        assert r.status_code == 400


class TestCommitDetailCache:
    """GET /commit/detail is served from a server-side LRU after the first hit."""

    def test_second_call_hits_cache(self, opened, client, monkeypatch):
        from app.services import git_reader

        sha = client.get("/history", params={"path": opened, "limit": 1}).json()["items"][0]["sha"]
        # Reset the in-process cache to count a single git call.
        git_reader.clear_detail_cache()
        calls = []
        real = git_reader._run

        def spy(repo_path, args, **kwargs):
            calls.append(args[0] if args else "")
            return real(repo_path, args, **kwargs)

        monkeypatch.setattr(git_reader, "_run", spy)
        r1 = client.get("/commit/detail", params={"path": opened, "sha": sha})
        r2 = client.get("/commit/detail", params={"path": opened, "sha": sha})
        assert r1.status_code == 200
        assert r2.status_code == 200
        # The second call must NOT have spawned another `git show`.
        show_calls = [c for c in calls if c == "show"]
        assert len(show_calls) == 1, f"expected 1 git show, got {len(show_calls)}: {calls}"

    def test_invalid_sha_not_cached(self, opened, client):
        from app.services import git_reader

        git_reader.clear_detail_cache()
        r = client.get("/commit/detail", params={"path": opened, "sha": "zzzz"})
        assert r.status_code == 400
        # Caller's error path must not poison the cache.
        git_reader.clear_detail_cache()


class TestRemoteStatus:
    def test_unparseable_url_is_distinct_from_no_origin(self, opened, client, tmp_path, monkeypatch):
        from app.services import git_reader

        repo = tmp_path / "bad-remote"
        repo.mkdir()
        monkeypatch.setattr(git_reader, "_run", lambda *a, **k: "ftp://example.com/x\n")
        status, url = git_reader.read_remote(str(repo))
        assert status == git_reader.RemoteStatus.UNPARSEABLE
        assert url is None

    def test_no_origin_keeps_status(self, opened, client, tmp_path, monkeypatch):
        from app.services import git_reader
        from app.services.git_reader import GitError

        repo = tmp_path / "no-origin"
        repo.mkdir()
        monkeypatch.setattr(git_reader, "_run", lambda *a, **k: (_ for _ in ()).throw(GitError("missing")))
        status, url = git_reader.read_remote(str(repo))
        assert status == git_reader.RemoteStatus.NO_ORIGIN
        assert url is None
