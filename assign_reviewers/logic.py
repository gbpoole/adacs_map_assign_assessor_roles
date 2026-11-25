"""Assign a Lead Assessor and Co-Assessors to each proposal.

Pure domain logic: standard library only, no file or CLI handling. Every list
passed in or returned is parallel to ``proposals`` (same length, same order).
See GLOSSARY.md for the terms used here.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import combinations


class _Conflict:
    """Sentinel type for a declared Conflict in place of a Mark."""

    _instance: _Conflict | None = None

    def __new__(cls) -> _Conflict:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "CONFLICT"


CONFLICT = _Conflict()

Mark = float | _Conflict | None


@dataclass(frozen=True)
class Proposal:
    title: str
    marks: Mapping[str, Mark] = field(default_factory=dict)


@dataclass(frozen=True)
class Problem:
    """One reason the inputs are invalid; ``index`` is the position in ``proposals``, if any."""

    message: str
    index: int | None = None

    def __str__(self) -> str:
        return self.message if self.index is None else f"proposal at position {self.index}: {self.message}"


class AssignmentError(Exception):
    """Base class: the inputs cannot produce a valid assignment.

    ``problems`` lists every problem found, so they can all be fixed at once.
    """

    def __init__(self, problems: Sequence[Problem]):
        self.problems = list(problems)
        super().__init__("\n".join(map(str, self.problems)))


class InvalidPreassignmentError(AssignmentError):
    """A Pre-assignment is malformed (unknown assessor, duplicate role, too many Co-Assessors)."""


class IneligiblePreassignmentError(AssignmentError):
    """A Pre-assignment gives a role to an assessor who is Ineligible for that proposal."""


class InsufficientAssessorsError(AssignmentError):
    """A proposal has too few eligible assessors to fill every role."""


def is_eligible(proposal: Proposal, assessor: str) -> bool:
    """An assessor is eligible unless they have a Conflict or a Non-submission (blank or zero)."""
    mark = proposal.marks.get(assessor)
    return mark is not None and mark is not CONFLICT and mark != 0


def eligible_assessors(proposal: Proposal, assessors: Sequence[str]) -> list[str]:
    return [a for a in assessors if is_eligible(proposal, a)]


def mean_mark(proposal: Proposal) -> float | None:
    """Mean of the Marks from eligible assessors, or None if there are none."""
    marks = [m for a, m in proposal.marks.items() if is_eligible(proposal, a)]
    return sum(marks) / len(marks) if marks else None


def mark_order(proposals: Sequence[Proposal]) -> list[int]:
    """Proposal positions from highest to lowest Mean Mark; ties keep input order."""
    means = [mean_mark(p) for p in proposals]
    return sorted(
        range(len(proposals)),
        key=lambda i: (means[i] is None, -(means[i] or 0.0)),
    )


def assign(
    assessors: Sequence[str],
    proposals: Sequence[Proposal],
    preassigned_leads: Sequence[str | None] | None = None,
    preassigned_co_assessors: Sequence[Sequence[str]] | None = None,
    n_co_assessors: int = 2,
    seed: int = 0,
) -> tuple[list[str], list[list[str]]]:
    """Return (leads, co_assessors), parallel to ``proposals``.

    Hard rules: no assessor gets a role on a proposal they are Ineligible for,
    and nobody is both Lead and Co-Assessor on the same proposal. Pre-assigned
    roles are kept and count toward each assessor's Load.

    Leads are handed out in Mean Mark order, rotating through ``assessors``
    and favouring whoever has led least, so each assessor's Leads spread
    across the mark range. Co-Assessors are then chosen to even out total
    Load, then Co-Assessor Load, then to avoid repeating the same pairings;
    remaining ties are broken by a random draw seeded with ``seed``.
    """
    n = len(proposals)
    pre_leads = list(preassigned_leads) if preassigned_leads is not None else [None] * n
    pre_cos = (
        [list(c) for c in preassigned_co_assessors]
        if preassigned_co_assessors is not None
        else [[] for _ in range(n)]
    )
    _validate(assessors, proposals, pre_leads, pre_cos, n_co_assessors)

    rng = random.Random(seed)
    order = mark_order(proposals)
    lead_load: Counter[str] = Counter(a for a in pre_leads if a is not None)
    co_load: Counter[str] = Counter(a for cos in pre_cos for a in cos)

    leads: list[str | None] = list(pre_leads)
    position = {a: k for k, a in enumerate(assessors)}
    next_up = 0
    for i in order:
        if leads[i] is not None:
            continue
        candidates = [a for a in eligible_assessors(proposals[i], assessors) if a not in pre_cos[i]]
        lead = min(
            candidates,
            key=lambda a: (lead_load[a], (position[a] - next_up) % len(assessors)),
        )
        leads[i] = lead
        lead_load[lead] += 1
        next_up = (position[lead] + 1) % len(assessors)

    pair_count: Counter[frozenset[str]] = Counter()
    co_assessors: list[list[str]] = [list(c) for c in pre_cos]
    for i in order:
        team = [leads[i], *co_assessors[i]]
        while len(co_assessors[i]) < n_co_assessors:
            candidates = [a for a in eligible_assessors(proposals[i], assessors) if a not in team]
            draws = {a: rng.random() for a in candidates}
            pick = min(
                candidates,
                key=lambda a: (
                    lead_load[a] + co_load[a],
                    co_load[a],
                    sum(pair_count[frozenset((a, t))] for t in team),
                    draws[a],
                ),
            )
            co_assessors[i].append(pick)
            co_load[pick] += 1
            team.append(pick)
        pair_count.update(frozenset(p) for p in combinations(team, 2))

    return [lead for lead in leads if lead is not None], co_assessors


def _validate(
    assessors: Sequence[str],
    proposals: Sequence[Proposal],
    pre_leads: Sequence[str | None],
    pre_cos: Sequence[Sequence[str]],
    n_co_assessors: int,
) -> None:
    """Raise one AssignmentError describing every problem with the inputs."""
    if n_co_assessors < 0:
        raise InvalidPreassignmentError([Problem(f"n_co_assessors must be >= 0, got {n_co_assessors}")])
    if len(pre_leads) != len(proposals) or len(pre_cos) != len(proposals):
        raise InvalidPreassignmentError(
            [
                Problem(
                    f"Pre-assignment lists must match the {len(proposals)} proposals "
                    f"(got {len(pre_leads)} leads, {len(pre_cos)} co-assessor lists)"
                )
            ]
        )

    known = set(assessors)
    invalid: list[Problem] = []
    ineligible: list[Problem] = []
    insufficient: list[Problem] = []
    for i, (proposal, lead, cos) in enumerate(zip(proposals, pre_leads, pre_cos)):
        named = ([lead] if lead is not None else []) + list(cos)
        for a in named:
            if a not in known:
                invalid.append(Problem(f"unknown assessor {a!r}", i))
            elif not is_eligible(proposal, a):
                ineligible.append(Problem(f"{a} is Ineligible but was pre-assigned", i))
        if lead is not None and lead in cos:
            invalid.append(Problem(f"{lead} pre-assigned as both Lead and Co-Assessor", i))
        if len(set(cos)) != len(cos):
            invalid.append(Problem("duplicate pre-assigned Co-Assessor", i))
        if len(cos) > n_co_assessors:
            invalid.append(
                Problem(f"{len(cos)} Co-Assessors pre-assigned but only {n_co_assessors} required", i)
            )
        eligible = eligible_assessors(proposal, assessors)
        if len(eligible) < 1 + n_co_assessors:
            insufficient.append(
                Problem(
                    f"needs {1 + n_co_assessors} eligible assessors, "
                    f"has {len(eligible)} ({', '.join(eligible) or 'none'})",
                    i,
                )
            )

    found = [
        (cls, problems)
        for cls, problems in (
            (InvalidPreassignmentError, invalid),
            (IneligiblePreassignmentError, ineligible),
            (InsufficientAssessorsError, insufficient),
        )
        if problems
    ]
    if len(found) == 1:
        cls, problems = found[0]
        raise cls(problems)
    if found:
        raise AssignmentError([msg for _, problems in found for msg in problems])
