from __future__ import annotations

from memory_mcp.utils.rrf import rrf_fuse


def test_rrf_fusion():
    rankings = [["a", "b", "c"], ["b", "a", "d"]]
    scores = rrf_fuse(rankings, k=60)
    assert scores["a"] > scores["c"]
    assert scores["b"] > scores["d"]
