"""Lane layout engine — assigns swimlanes to commits and emits draw segments.

Branch identity flows DOWNWARD from children to parents (expected-sha
mechanism): a commit is displayed on the branch that expects it; its main
parent inherits the branch, secondary parents get fresh branches. When a
merge target is claimed, its whole not-yet-displayed first-parent-child
chain is claimed with it (feature commits above the merge base share the
feature lane). This keeps fork/merge structures visible.

Row geometry contract (row-local y in [0, ROW_HEIGHT], y grows downward):
  - the node sits at (x, 16) on its branch lane;
  - the top edge of a row is the bottom edge of the previous row, so every
    segment is drawn with the branch positions valid on its side of the row;
  - a lane death at row i shifts survivors left starting at row i; branches
    that shift draw S-curves across the row so paths stay continuous — no
    broken angles (PLAN 5.3/8.3).

Segment types:
  - "vertical": straight piece (x1 == x2),
  - "curve": cubic bezier with vertical tangents (cx1/cx2 == x1/x2), covering
    trunk shifts (top->node), merge/fork links and handovers (node->bottom
    edge, landing on the target lane at the next row's top).

Colors bind to the branch at creation and never change, even when the branch
lane index shifts (PLAN 2.4 "couleurs stables").
"""
from __future__ import annotations

from dataclasses import dataclass, field

ROW_HEIGHT = 32.0
NODE_Y = ROW_HEIGHT / 2.0
LANE_GAP = 20.0
NODE_R = 4.5
LINE_W = 2.0
FIRST_LANE_X = 24.0

LANE_COLORS = [
    "#f79ac0", "#8dd3ff", "#9ee6b5", "#ffd48a", "#c3b6ff", "#ffb2a6",
    "#94e2d5", "#b7e48a", "#f6b0e5", "#a0c4ff", "#ffd6a5", "#caffbf",
]


def lane_color(index: int) -> str:
    return LANE_COLORS[index % len(LANE_COLORS)]


def lane_x(index: int) -> float:
    return FIRST_LANE_X + index * LANE_GAP


@dataclass
class LayoutRow:
    sha: str
    lane_index: int          # branch lane at this row (post-shift position)
    node: dict
    segments: list[dict] = field(default_factory=list)


@dataclass
class _Branch:
    key: str                 # sha of the commit that created it
    color_idx: int
    lane: int = -1           # current lane (mutated after each row)


def compute_layout(
    shas: list[str],
    parents_map: dict[str, list[str]],
) -> tuple[list[LayoutRow], int]:
    known = set(shas)
    # First-parent children: child commits whose FIRST parent is the key.
    fp_children: dict[str, list[str]] = {}
    for sha in shas:
        parents = parents_map.get(sha, [])
        if parents and parents[0] in known:
            fp_children.setdefault(parents[0], []).append(sha)

    expected: dict[str, _Branch] = {}   # sha -> branch that will display it
    displayed: set[str] = set()
    occupied: list[_Branch] = []        # lane order (index == lane)
    next_color = 0
    rows: list[LayoutRow] = []
    max_lane = 0

    def new_branch(key: str) -> _Branch:
        nonlocal next_color
        b = _Branch(key=key, color_idx=next_color, lane=-1)
        next_color += 1
        return b  # appended to `occupied` during the commit phase

    def claim_chain(branch: _Branch, start: str) -> None:
        """Claim `start` (already owned by `branch`) and walk upward through
        its first-parent children, claiming every commit not yet claimed by
        another branch — feature commits above the merge base share the lane.
        """
        cur: str | None = start
        while cur is not None and cur in known and cur not in displayed:
            owner = expected.get(cur)
            if owner is not None and owner is not branch:
                break
            expected[cur] = branch
            children = [c for c in fp_children.get(cur, []) if c in known]
            cur = children[0] if children else None

    for row_idx, sha in enumerate(shas):
        branch = expected.pop(sha, None)
        first_appearance = branch is None
        if first_appearance:
            branch = new_branch(sha)

        parents: list[str] = []
        for p in parents_map.get(sha, []):
            if p in known and p not in parents:
                parents.append(p)
        first = parents[0] if parents else None

        continues = False
        handover_to: _Branch | None = None
        if first is not None:
            heir = expected.get(first)
            if heir is None:
                # Main parent unclaimed: this branch hands down to it.
                expected[first] = branch
                continues = True
            elif heir is branch:
                # Already ours (claimed via the upstream chain): continue.
                continues = True
            else:
                # Main parent claimed by another branch (merge target):
                # this branch dies and curves into that lane.
                handover_to = heir

        # Secondary parents: reuse the branch that already expects them
        # (merge-back), otherwise spawn a branch and claim its upstream
        # first-parent chain (feature commits above the merge base).
        targets: list[_Branch] = []
        created: list[_Branch] = []
        for p in parents[1:]:
            if p not in expected:
                b = new_branch(p)
                expected[p] = b
                created.append(b)
                claim_chain(b, p)
            targets.append(expected[p])

        # --- positions (pre = top edge, post = bottom edge of this row) ---
        # Survivors keep their relative order (compacted when a lane dies),
        # then the current branch if it appears this row, then forks spawned
        # this row (they curve out from the current node, to its right).
        pre = {id(b): b.lane for b in occupied}
        dying = None if continues else branch
        post: dict[int, int] = {}
        idx = 0
        for b in occupied:
            if b is dying:
                continue
            post[id(b)] = idx
            idx += 1
        if first_appearance:
            post[id(branch)] = idx
            idx += 1
        for b in created:
            post[id(b)] = idx
            idx += 1

        lane_pre = pre.get(id(branch), -1)
        # A dying branch keeps its old lane for the node geometry.
        lane_post = post.get(id(branch), lane_pre)
        x_pre = lane_x(lane_pre)
        x_node = lane_x(lane_post)
        color = lane_color(branch.color_idx)
        segments: list[dict] = []

        # Pass-through lanes (drawn behind nodes): S-curve when the branch
        # shifts this row, straight otherwise.
        for b in occupied:
            if b is branch or b is dying or id(b) not in post:
                continue
            xp, xn = lane_x(pre[id(b)]), lane_x(post[id(b)])
            if xp == xn:
                segments.append(_vertical(xn, 0.0, xn, ROW_HEIGHT, lane_color(b.color_idx)))
            else:
                segments.append(_curve(xp, 0.0, xn, ROW_HEIGHT, lane_color(b.color_idx)))

        # Trunk into the node (branches appearing this row start at the node).
        if not first_appearance:
            if lane_pre == lane_post:
                segments.append(_vertical(x_node, 0.0, x_node, NODE_Y, color))
            else:
                segments.append(_curve(x_pre, 0.0, x_node, NODE_Y, color))
        # Trunk out of the node (flows to the window edge while the branch
        # continues below).
        if continues:
            segments.append(_vertical(x_node, NODE_Y, x_node, ROW_HEIGHT, color))

        # Merge/fork curves: node -> row bottom edge, landing on the target's
        # post-shift lane (= next row's top edge position).
        for t in targets:
            segments.append(_curve(x_node, NODE_Y, lane_x(post[id(t)]), ROW_HEIGHT, color))

        # Handover curve: dying branch joins the heir branch's lane below.
        if handover_to is not None:
            segments.append(_curve(x_node, NODE_Y, lane_x(post[id(handover_to)]), ROW_HEIGHT, color))

        node = {"x": x_node, "y": NODE_Y, "r": NODE_R, "color": color}
        rows.append(LayoutRow(sha=sha, lane_index=lane_post, node=node, segments=segments))
        max_lane = max(max_lane, lane_post, *(post[id(t)] for t in targets))

        # --- commit positions for the next row -------------------------
        # Rebuild `occupied` in lane order: survivors, current branch (when
        # it appears this row and survives), then branches spawned this row.
        next_occupied: list[_Branch] = []
        for b in occupied:
            if b is dying:
                continue
            b.lane = post[id(b)]
            next_occupied.append(b)
        if first_appearance and branch is not dying:
            branch.lane = post[id(branch)]
            next_occupied.append(branch)
        for b in created:
            b.lane = post[id(b)]
            next_occupied.append(b)
        occupied = next_occupied
        displayed.add(sha)

    return rows, max_lane


def _vertical(x1: float, y1: float, x2: float, y2: float, color: str) -> dict:
    return {"type": "vertical", "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "color": color, "w": LINE_W}


def _curve(x1: float, y1: float, x2: float, y2: float, color: str) -> dict:
    mid = (y1 + y2) / 2.0
    return {
        "type": "curve", "x1": x1, "y1": y1, "x2": x2, "y2": y2,
        "cx1": x1, "cy1": mid, "cx2": x2, "cy2": mid,
        "color": color, "w": LINE_W,
    }
