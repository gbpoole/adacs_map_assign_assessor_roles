# Assessor Assignment

Allocating assessors to proposals after the marking round, so that each proposal gets one assessor who leads its assessment and two who support it.

## Language

### People and proposals

**Proposal**:
An application under assessment. Titles need not be unique.
_Avoid_: Application, submission, project

**Assessor**:
A person who marks proposals.
_Avoid_: Reviewer, marker, panel member

**Mark**:
The numeric score an assessor gives a proposal.
_Avoid_: Score, grade, rating

**Mean Mark**:
The average of the marks given to a proposal by its eligible assessors. It decides where the proposal sits in the mark range.
_Avoid_: Average score, overall mark

### Eligibility

**Conflict**:
A declared reason an assessor cannot assess a proposal, recorded as `X` in place of a mark.
_Avoid_: Conflict of interest (in code), recusal

**Non-submission**:
The assessor gave no mark for a proposal (a blank or zero).
_Avoid_: Missing mark, abstention

**Ineligible**:
The assessor has a Conflict or a Non-submission for the proposal, so they cannot hold any role on it.
_Avoid_: Excluded, blocked, conflicted (when Non-submission is the reason)

### Roles

**Lead Assessor**:
The single assessor who leads the assessment of a proposal.
_Avoid_: Primary, lead reviewer

**Co-Assessor**:
An assessor who supports the Lead Assessor on a proposal. Never the same person as that proposal's Lead. There are usually two per proposal, but the number can be anywhere from zero up.
_Avoid_: Secondary, co-reviewer

**Assignment**:
The full set of roles for one proposal: one Lead Assessor and its Co-Assessors.
_Avoid_: Allocation

**Proposal Index**:
A proposal's position in the proposals list. It identifies the proposal in every file.
_Avoid_: Proposal ID, row number (in prose)

**Pre-assignment**:
A role fixed by hand before the automatic assignment runs. The algorithm must keep it and must not override it.
_Avoid_: Override, manual assignment

**Load**:
The number of roles an assessor holds across all proposals, counted separately for Lead and Co-Assessor.
_Avoid_: Workload, quota
