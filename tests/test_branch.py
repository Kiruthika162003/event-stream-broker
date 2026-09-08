from __future__ import annotations

from relay.branch import Brancher


def _brancher(default=None):
    return Brancher(
        branches=[
            ("high", lambda v: v >= 1000),
            ("mid", lambda v: v >= 100),
            ("low", lambda v: v >= 0),
        ],
        default=default,
    )


class TestRoute:
    def test_first_match_wins(self):
        b = _brancher()
        assert b.route(5000) == "high"
        assert b.route(500) == "mid"
        assert b.route(5) == "low"

    def test_order_decides_which_branch_captures(self):
        # a broad predicate first captures what a later narrow one wanted
        b = Brancher(
            branches=[
                ("broad", lambda v: v >= 0),
                ("narrow", lambda v: v >= 1000),
            ]
        )
        assert b.route(5000) == "broad"
        assert b.starved() == ["narrow"]

    def test_no_match_drops_without_a_default(self):
        b = Brancher(branches=[("pos", lambda v: v > 0)])
        assert b.route(-5) == "<dropped>"

    def test_no_match_goes_to_the_default_when_set(self):
        b = Brancher(
            branches=[("pos", lambda v: v > 0)],
            default="other",
        )
        assert b.route(-5) == "other"


class TestDistribution:
    def test_distribution_counts_each_branch(self):
        b = _brancher()
        for v in (5000, 500, 5, 5):
            b.route(v)
        note = b.distribution()
        assert "high: 1" in note
        assert "low: 2" in note
