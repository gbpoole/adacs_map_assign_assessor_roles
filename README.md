# assign-reviewers

Prototype that assigns a Lead Assessor and Co-Assessors to every proposal, never
assigning anyone to a proposal they are Ineligible for. See `GLOSSARY.md` for terms.

- `assign_reviewers/logic.py`: all domain logic, standard library only (destined for Django).
- `assign_reviewers/cli.py`: Click commands and all CSV I/O.

```sh
python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/assign-reviewers assign proposals.csv [--preassign pre.csv] [--co-assessors N] [--seed N] [--output out.csv]
.venv/bin/assign-reviewers prefill proposals.csv pre.csv [--co-assessors N]
.venv/bin/pytest
```

Pre-assignment CSV columns:

- `Proposal Index`: the 1-based data row in the proposals CSV. This is the key.
- `Title`: for human readers; ignored on read.
- `Lead Assessor`
- `Co-Assessors`: names separated by `;`.

The `--output` file uses the same format, so you can edit it and feed it back in with `--preassign`.
