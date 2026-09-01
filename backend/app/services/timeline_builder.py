"""Mini timeline aggregation: commit activity buckets for the sparkline."""
from __future__ import annotations

DEFAULT_BUCKETS = 90


def build_timeline(
    timestamps: list[int],
    buckets: int = DEFAULT_BUCKETS,
    additions: list[int] | None = None,
    deletions: list[int] | None = None,
) -> dict:
    if not timestamps:
        return {"t_min": None, "t_max": None, "points": []}
    t_min = min(timestamps)
    t_max = max(timestamps)
    span = max(1, t_max - t_min)
    counts = [0] * buckets
    adds_bucket = [0] * buckets
    dels_bucket = [0] * buckets
    for i, t in enumerate(timestamps):
        b = int((t - t_min) * buckets / span)
        b = min(b, buckets - 1)
        counts[b] += 1
        if additions:
            adds_bucket[b] += additions[i]
        if deletions:
            dels_bucket[b] += deletions[i]
    points = [
        {
            "t": t_min + round((i + 0.5) * span / buckets),
            "count": c,
            "adds": adds_bucket[i],
            "dels": dels_bucket[i],
        }
        for i, c in enumerate(counts)
    ]
    return {"t_min": t_min, "t_max": t_max, "points": points}
