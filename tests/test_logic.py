from collections import Counter
from itertools import combinations

import pytest

from assign_reviewers.logic import (
    CONFLICT,
    AssignmentError,
    IneligiblePreassignmentError,
    InsufficientAssessorsError,
    InvalidPreassignmentError,
    Proposal,
    assign,
    is_eligible,
    mark_order,
    mean_mark,
    summarise_load,
)

ASSESSORS = ["A", "B", "C", "D", "E", "F"]


def make(marks_by_proposal: list[dict]) -> list[Proposal]:
    return [Proposal(f"P{i}", m) for i, m in enumerate(marks_by_proposal)]


def full_panel(n: int, seed: int = 1) -> list[Proposal]:
    """n proposals, every assessor marks every one, with varied marks."""
    return make([{a: (i * 7 + k * 3 + seed) % 10 + 1 for k, a in enumerate(ASSESSORS)} for i in range(n)])


def check_hard_rules(proposals, leads, cos, n_co=2):
    assert len(leads) == len(cos) == len(proposals)
    for p, lead, co in zip(proposals, leads, cos):
        assert len(co) == n_co
        team = [lead, *co]
        assert len(set(team)) == len(team), "nobody holds two roles on one proposal"
        assert all(is_eligible(p, a) for a in team), "no Ineligible assessor assigned"


def test_eligibility_rules():
    p = Proposal("P", {"A": 5, "B": CONFLICT, "C": None, "D": 0})
    assert is_eligible(p, "A")
    assert not is_eligible(p, "B")
    assert not is_eligible(p, "C")
    assert not is_eligible(p, "D")
    assert not is_eligible(p, "Z")
    assert mean_mark(p) == 5


def test_mark_order_ties_keep_input_order():
    proposals = make([{"A": 5}, {"A": 9}, {"A": 5}, {"A": 9}])
    assert mark_order(proposals) == [1, 3, 0, 2]


def test_conflicts_and_non_submissions_never_assigned():
    proposals = full_panel(30)
    marks = [dict(p.marks) for p in proposals]
    for i, m in enumerate(marks):
        m[ASSESSORS[i % 6]] = CONFLICT
        m[ASSESSORS[(i + 2) % 6]] = 0
    proposals = make(marks)
    leads, cos = assign(ASSESSORS, proposals)
    check_hard_rules(proposals, leads, cos)


def test_leads_balanced_and_spread_across_marks():
    proposals = full_panel(36)
    leads, cos = assign(ASSESSORS, proposals)
    check_hard_rules(proposals, leads, cos)
    assert set(Counter(leads).values()) == {6}
    order = mark_order(proposals)
    for third in (order[:12], order[12:24], order[24:]):
        assert set(Counter(leads[i] for i in third).values()) == {2}


def test_total_load_balanced():
    proposals = full_panel(30)
    leads, cos = assign(ASSESSORS, proposals)
    load = Counter(leads) + Counter(a for c in cos for a in c)
    assert max(load.values()) - min(load.values()) <= 1


def test_pairings_vary():
    proposals = full_panel(30)
    leads, cos = assign(ASSESSORS, proposals)
    pairs = Counter(frozenset(p) for lead, c in zip(leads, cos) for p in combinations([lead, *c], 2))
    assert len(pairs) == 15  # every possible pair of 6 assessors occurs


def test_summarise_load():
    proposals = make([{"A": 9}, {"A": 1}, {"A": 5}])  # Mean Mark ranks: P0 high, P2 mid, P1 low
    loads = summarise_load(["A", "B", "C"], proposals, ["A", "A", "B"], [["B", "C"], ["C"], []])
    assert [(l.assessor, l.leads, l.co_assessments, l.total, l.leads_by_tercile) for l in loads] == [
        ("A", 2, 0, 2, (1, 0, 1)),
        ("B", 1, 1, 2, (0, 1, 0)),
        ("C", 0, 2, 2, (0, 0, 0)),
    ]


def test_deterministic_for_seed():
    proposals = full_panel(20)
    assert assign(ASSESSORS, proposals, seed=3) == assign(ASSESSORS, proposals, seed=3)


@pytest.mark.parametrize("n_co", [0, 1, 3])
def test_co_assessor_count(n_co):
    proposals = full_panel(12)
    leads, cos = assign(ASSESSORS, proposals, n_co_assessors=n_co)
    check_hard_rules(proposals, leads, cos, n_co)


def test_preassignments_kept_and_completed():
    proposals = full_panel(6)
    pre_leads = ["A", None, None, None, None, None]
    pre_cos = [[], ["A", "B"], ["C"], [], [], []]
    leads, cos = assign(ASSESSORS, proposals, pre_leads, pre_cos)
    check_hard_rules(proposals, leads, cos)
    assert leads[0] == "A"
    assert cos[1] == ["A", "B"]
    assert cos[2][0] == "C"


def test_preassignment_of_ineligible_assessor_rejected():
    proposals = make([{"A": CONFLICT, "B": 5, "C": 5, "D": 5}])
    with pytest.raises(IneligiblePreassignmentError):
        assign(["A", "B", "C", "D"], proposals, ["A"], [[]])


def test_invalid_preassignments_rejected():
    proposals = make([{a: 5 for a in "ABCD"}])
    for leads, cos in [(["Z"], [[]]), (["A"], [["A"]]), ([None], [["B", "B"]]), ([None], [["B", "C", "D"]])]:
        with pytest.raises(InvalidPreassignmentError):
            assign(["A", "B", "C", "D"], proposals, leads, cos)


def test_insufficient_assessors_lists_every_proposal():
    proposals = make([{"A": 5, "B": 5}, {"A": 5, "B": 5, "C": 5}, {"A": CONFLICT, "B": 5}])
    with pytest.raises(InsufficientAssessorsError) as exc:
        assign(["A", "B", "C"], proposals)
    assert len(exc.value.problems) == 2


def test_mixed_problems_raise_base_error_with_all_problems():
    proposals = make([{"A": 5, "B": 5}, {"A": CONFLICT, "B": 5, "C": 5, "D": 5}])
    with pytest.raises(AssignmentError) as exc:
        assign(["A", "B", "C", "D"], proposals, [None, "A"], [[], []])
    assert type(exc.value) is AssignmentError
    assert len(exc.value.problems) == 2
