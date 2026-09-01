"""Unit tests for the lane layout engine (PLAN.md section 8.4 cases)."""
from __future__ import annotations

import pytest

from app.services.lane_layout import (
    NODE_Y,
    ROW_HEIGHT,
    compute_layout,
    lane_x,
)


def _run(graph: dict[str, list[str]], order: list[str]):
    return compute_layout(order, graph)


def _row_by_sha(rows):
    return {r.sha: r for r in rows}


class TestLinear:
    def test_single_lane_end_to_end(self):
        g = {"c3": ["c2"], "c2": ["c1"], "c1": []}
        rows, max_lane = _run(g, ["c3", "c2", "c1"])
        assert max_lane == 0
        assert all(r.lane_index == 0 for r in rows)
        # Every row has a node centered on lane 0, y mid-height.
        for r in rows:
            assert r.node["x"] == lane_x(0)
            assert r.node["y"] == NODE_Y

    def test_trunk_continuity(self):
        """Vertical pieces join exactly across row boundaries."""
        g = {f"c{i}": [f"c{i-1}"] for i in range(2, 6)}
        g["c1"] = []
        rows, _ = _run(g, [f"c{i}" for i in range(5, 0, -1)])
        x = lane_x(0)
        for i in range(len(rows) - 1):
            bottoms = [s for s in rows[i].segments if abs(s["y2"] - ROW_HEIGHT) < 1e-6 and s["x2"] == x]
            tops = [s for s in rows[i + 1].segments if abs(s["y1"]) < 1e-6 and s["x1"] == x]
            assert bottoms, f"row {i} lacks bottom trunk piece"
            assert tops, f"row {i+1} lacks top trunk piece"


class TestSingleMerge:
    def test_feature_lane_and_merge_curve(self):
        # Display (topo): M, A(main), B(feature). M parents: [A, B].
        g = {"M": ["A", "B"], "A": ["R"], "B": ["R"], "R": []}
        rows, max_lane = _run(g, ["M", "A", "B", "R"])
        by = _row_by_sha(rows)
        # M and A share the main lane (0); B sits on a second lane.
        assert by["M"].lane_index == 0
        assert by["A"].lane_index == 0
        assert by["B"].lane_index == 1
        assert max_lane == 1
        # M's row carries a merge curve leaving toward lane 1.
        curves = [s for s in by["M"].segments if s["type"] == "curve"]
        assert any(abs(s["x2"] - lane_x(1)) < 1e-6 for s in curves), "no curve to feature lane"
        # B flows back into main: B's row curves into lane 0 (B is root here
        # only visually — R is the shared root displayed last).
        curves_b = [s for s in by["B"].segments if s["type"] == "curve"]
        assert any(abs(s["x2"] - lane_x(0)) < 1e-6 for s in curves_b), "feature lane never merges back"


class TestLongBranchThenMerge:
    def test_branch_lane_stable_then_returns(self):
        # Display: M, A2, A1(main chain), F3, F2, F1(feature), R.
        g = {
            "M": ["A1", "F1"],
            "A1": ["R"],
            "F1": ["R"],
            "F2": ["F1"],
            "F3": ["F2"],
            "R": [],
        }
        order = ["M", "A1", "F3", "F2", "F1", "R"]
        rows, max_lane = _run(g, order)
        by = _row_by_sha(rows)
        assert max_lane == 1
        assert by["M"].lane_index == 0
        assert by["A1"].lane_index == 0
        feature = [by[s].lane_index for s in ("F3", "F2", "F1")]
        assert feature == [1, 1, 1], "feature lane must be stable along the branch"
        # F1 (feature tip, parent R already expected by main) hands over.
        curves = [s for s in by["F1"].segments if s["type"] == "curve"]
        assert any(abs(s["x2"] - lane_x(0)) < 1e-6 for s in curves)


class TestOctopus:
    def test_three_parents_three_lanes(self):
        # Display: X(merge of A1,A2,A3), A1, A2, A3, R.
        g = {
            "X": ["A1", "A2", "A3"],
            "A1": ["R"],
            "A2": ["R"],
            "A3": ["R"],
            "R": [],
        }
        rows, max_lane = _run(g, ["X", "A1", "A2", "A3", "R"])
        by = _row_by_sha(rows)
        assert by["X"].lane_index == 0
        # Octopus spawns two side lanes.
        assert max_lane == 2
        curves = [s for s in by["X"].segments if s["type"] == "curve"]
        dests = {round(s["x2"], 3) for s in curves}
        assert lane_x(1) in dests and lane_x(2) in dests
        # Each secondary parent row carries a lane and eventually joins main.
        for sha in ("A2", "A3"):
            cur = [s for s in by[sha].segments if s["type"] == "curve"]
            assert any(abs(s["x2"] - lane_x(0)) < 1e-6 for s in cur), f"{sha} never returns to main"

    def test_compaction_after_merge_back(self):
        g = {
            "X": ["A1", "A2", "A3"],
            "A1": ["R"],
            "A2": ["R"],
            "A3": ["R"],
            "R": [],
        }
        rows, max_lane = _run(g, ["X", "A1", "A2", "A3", "R"])
        # Once all branches returned, the root row is back to a single lane.
        assert rows[-1].lane_index == 0


class TestMultipleRoots:
    def test_second_root_gets_its_lane(self):
        # Two independent roots; display: C(merge), R1, R2.
        # At row R1: main lane (0) + R2's branch lane (1). At R2: the main
        # branch died at R1 (R1 is a root), R2 shifts to lane 0 (compaction).
        g = {"C": ["R1", "R2"], "R1": [], "R2": []}
        rows, max_lane = _run(g, ["C", "R1", "R2"])
        by = _row_by_sha(rows)
        assert by["C"].lane_index == 0
        assert by["R1"].lane_index == 0
        assert by["R2"].lane_index == 0
        assert max_lane == 1

    def test_colors_stable_per_branch(self):
        g = {
            "M": ["A1", "F1"],
            "A1": ["R"],
            "F1": ["R"],
            "F2": ["F1"],
            "R": [],
        }
        rows, _ = _run(g, ["M", "A1", "F2", "F1", "R"])
        by = _row_by_sha(rows)
        # All commits on the feature branch share one color, main another.
        feature_colors = {by[s].node["color"] for s in ("F2", "F1")}
        main_colors = {by[s].node["color"] for s in ("M", "A1")}
        assert len(feature_colors) == 1
        assert len(main_colors) == 1
        assert feature_colors != main_colors


class TestGeometry:
    def test_segments_stay_within_row(self):
        g = {"M": ["A", "B"], "A": ["R"], "B": ["R"], "R": []}
        rows, _ = _run(g, ["M", "A", "B", "R"])
        for r in rows:
            for s in r.segments:
                assert 0.0 <= s["y1"] <= ROW_HEIGHT
                assert 0.0 <= s["y2"] <= ROW_HEIGHT
                for k in ("cx1", "cx2"):
                    if s.get(k) is not None:
                        assert s[k] >= 0

    def test_curves_have_vertical_tangents(self):
        g = {"M": ["A", "B"], "A": ["R"], "B": ["R"], "R": []}
        rows, _ = _run(g, ["M", "A", "B", "R"])
        for r in rows:
            for s in r.segments:
                if s["type"] == "curve":
                    assert s["cx1"] == s["x1"] and s["cx2"] == s["x2"]

    def test_empty_history(self):
        rows, max_lane = _run({}, [])
        assert rows == [] and max_lane == 0


if __name__ == "__main__":
    pytest.main([__file__])
