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

## Sample data

`examples/` has fully synthetic inputs for trying the tool. Every name, title, institution and
email in them is invented, and the emails use the reserved `example.edu` domain.

```sh
.venv/bin/assign-reviewers assign examples/sample_proposals.csv
.venv/bin/assign-reviewers assign examples/sample_proposals.csv --preassign examples/sample_preassign.csv
.venv/bin/assign-reviewers prefill examples/sample_proposals.csv my_preassign.csv
```

`sample_proposals.csv` has 15 proposals and 7 assessors, in the same column layout as a real
proposals file. It includes each case the tool handles:

- Conflicts (`X`) on most proposals.
- A blank mark on proposals 5 and 10, and a `0` on proposal 12. Both count as not submitted.
- An assessor (`Gale Dummy`) with no marks at all. The tool warns about them and never assigns them.
- A `Fit Concerns` entry on proposal 7. This is informational only and doesn't make the assessor Ineligible.

`sample_preassign.csv` fixes the Lead on proposal 3 and both Co-Assessors on proposal 8.
Pre-assigned roles are marked `*` in the output.
