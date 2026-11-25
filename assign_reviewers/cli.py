"""Command-line interface and all file I/O for assessor assignment.

Proposals are identified in every file by their 1-based Proposal Index, i.e.
their data-row position in the proposals CSV.
"""

from __future__ import annotations

import csv
from pathlib import Path

import click

from assign_reviewers import logic

NON_ASSESSOR_COLUMNS = {
    "Title",
    "Author",
    "Email",
    "Institution",
    "Fit Concerns",
    "Dev Req'd [weeks]",
    "Train Req'd [weeks]",
    "Assessment Node",
}
CONFLICT_MARKERS = {"X", "x"}

PREASSIGN_COLUMNS = ["Proposal Index", "Title", "Lead Assessor", "Co-Assessors"]
CO_SEPARATOR = ";"


# --- Reading and writing files ------------------------------------------------


def read_proposals(path: Path) -> tuple[list[str], list[logic.Proposal]]:
    """Return (assessors, proposals); assessors are the non-standard header columns."""
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames or []
        if "Title" not in header:
            raise click.ClickException(f"{path}: no 'Title' column")
        assessors = [c for c in header if c not in NON_ASSESSOR_COLUMNS]
        proposals = []
        for row_number, row in enumerate(reader, start=1):
            marks = {a: _parse_mark(row.get(a), path, row_number, a) for a in assessors}
            proposals.append(logic.Proposal(title=row["Title"].strip(), marks=marks))
    return assessors, proposals


def _parse_mark(raw: str | None, path: Path, row_number: int, assessor: str) -> logic.Mark:
    value = (raw or "").strip()
    if not value:
        return None
    if value in CONFLICT_MARKERS:
        return logic.CONFLICT
    try:
        return float(value)
    except ValueError:
        raise click.ClickException(
            f"{path}: proposal {row_number}, {assessor}: unrecognised mark {value!r}"
        ) from None


def read_preassignments(
    path: Path, proposals: list[logic.Proposal]
) -> tuple[list[str | None], list[list[str]]]:
    """Return Pre-assignments as lists parallel to ``proposals``."""
    leads: list[str | None] = [None] * len(proposals)
    cos: list[list[str]] = [[] for _ in proposals]
    seen: set[int] = set()
    with path.open(newline="", encoding="utf-8-sig") as f:
        for line, row in enumerate(csv.DictReader(f), start=2):
            try:
                index = int(row["Proposal Index"])
            except (KeyError, TypeError, ValueError):
                raise click.ClickException(f"{path}:{line}: bad or missing 'Proposal Index'") from None
            if not 1 <= index <= len(proposals):
                raise click.ClickException(
                    f"{path}:{line}: Proposal Index {index} out of range 1-{len(proposals)}"
                )
            if index in seen:
                raise click.ClickException(f"{path}:{line}: Proposal Index {index} appears twice")
            seen.add(index)
            title = (row.get("Title") or "").strip()
            if title and title != proposals[index - 1].title:
                click.secho(
                    f"Warning: {path}:{line}: title {title!r} does not match proposal {index} "
                    f"({proposals[index - 1].title!r}); using the index",
                    fg="yellow",
                    err=True,
                )
            lead = (row.get("Lead Assessor") or "").strip()
            leads[index - 1] = lead or None
            cos[index - 1] = _split_names(row.get("Co-Assessors"))
    return leads, cos


def write_assignments(
    path: Path,
    proposals: list[logic.Proposal],
    leads: list[str | None],
    cos: list[list[str]],
) -> None:
    """Write in Pre-assignment format, so an output file can be fed back in."""
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(PREASSIGN_COLUMNS)
        for index, (proposal, lead, co) in enumerate(zip(proposals, leads, cos), start=1):
            if lead is None and not co:
                continue
            writer.writerow([index, proposal.title, lead or "", CO_SEPARATOR.join(co)])


def _split_names(raw: str | None) -> list[str]:
    return [n.strip() for n in (raw or "").split(CO_SEPARATOR) if n.strip()]


# --- Terminal output ----------------------------------------------------------


def _print_table(headers: list[str], rows: list[list[str]], right_align: set[int] = frozenset()) -> None:
    widths = [max(len(str(x)) for x in col) for col in zip(headers, *rows)]

    def fmt(cells: list[str]) -> str:
        return "  ".join(
            str(c).rjust(w) if k in right_align else str(c).ljust(w)
            for k, (c, w) in enumerate(zip(cells, widths))
        ).rstrip()

    click.secho(fmt(headers), bold=True)
    click.echo("  ".join("-" * w for w in widths))
    for row in rows:
        click.echo(fmt(row))


def _truncate(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def print_assignments(
    proposals: list[logic.Proposal],
    leads: list[str],
    cos: list[list[str]],
    pre_leads: list[str | None],
    pre_cos: list[list[str]],
) -> None:
    rows = []
    for i, proposal in enumerate(proposals):
        mean = logic.mean_mark(proposal)
        star = lambda name, pre: f"{name}*" if name in pre else name  # noqa: E731
        rows.append(
            [
                str(i + 1),
                f"{mean:.1f}" if mean is not None else "-",
                _truncate(proposal.title, 50),
                star(leads[i], [pre_leads[i]]),
                ", ".join(star(c, pre_cos[i]) for c in cos[i]),
            ]
        )
    _print_table(["#", "Mean", "Title", "Lead", "Co-Assessors"], rows, right_align={0, 1})


def print_load(
    assessors: list[str],
    proposals: list[logic.Proposal],
    leads: list[str],
    cos: list[list[str]],
) -> None:
    """Per-assessor Load, with Leads split by thirds of the Mean Mark ranking."""
    order = logic.mark_order(proposals)
    tercile = {i: rank * 3 // len(order) for rank, i in enumerate(order)}
    rows = []
    for a in assessors:
        led = [i for i, lead in enumerate(leads) if lead == a]
        n_co = sum(a in c for c in cos)
        by_third = [sum(tercile[i] == t for i in led) for t in range(3)]
        rows.append([a, str(len(led)), str(n_co), str(len(led) + n_co), *map(str, by_third)])
    _print_table(
        ["Assessor", "Lead", "Co", "Total", "Lead-High", "Lead-Mid", "Lead-Low"],
        rows,
        right_align=set(range(1, 7)),
    )


def warn_unused_assessors(assessors: list[str], proposals: list[logic.Proposal]) -> None:
    for a in assessors:
        if not any(logic.is_eligible(p, a) for p in proposals):
            click.secho(
                f"Warning: {a} is Ineligible for every proposal and will not be assigned",
                fg="yellow",
                err=True,
            )


# --- Commands -----------------------------------------------------------------

proposals_argument = click.argument(
    "proposals_csv", type=click.Path(exists=True, dir_okay=False, path_type=Path)
)
co_assessors_option = click.option(
    "--co-assessors",
    "n_co",
    type=click.IntRange(min=0),
    default=2,
    show_default=True,
    help="Number of Co-Assessors per proposal.",
)


@click.group()
def cli() -> None:
    """Assign Lead and Co-Assessors to proposals, avoiding conflicts."""


@cli.command()
@proposals_argument
@co_assessors_option
@click.option(
    "--preassign",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Pre-assignment CSV (see the 'prefill' command).",
)
@click.option("--seed", type=int, default=0, show_default=True, help="Tie-break seed.")
@click.option(
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Also write the assignments to this CSV (Pre-assignment format).",
)
def assign(
    proposals_csv: Path, n_co: int, preassign: Path | None, seed: int, output: Path | None
) -> None:
    """Assign assessors to every proposal in PROPOSALS_CSV."""
    assessors, proposals = read_proposals(proposals_csv)
    warn_unused_assessors(assessors, proposals)
    if preassign:
        pre_leads, pre_cos = read_preassignments(preassign, proposals)
    else:
        pre_leads, pre_cos = [None] * len(proposals), [[] for _ in proposals]

    try:
        leads, cos = logic.assign(assessors, proposals, pre_leads, pre_cos, n_co, seed)
    except logic.AssignmentError as e:
        click.secho(f"Cannot assign ({type(e).__name__}):", fg="red", err=True)
        for problem in e.problems:
            where = (
                f"proposal {problem.index + 1} ({_truncate(proposals[problem.index].title, 40)!r}): "
                if problem.index is not None
                else ""
            )
            click.echo(f"  - {where}{problem.message}", err=True)
        raise SystemExit(1) from None

    click.echo()
    print_assignments(proposals, leads, cos, pre_leads, pre_cos)
    if preassign:
        click.echo("* = pre-assigned")
    click.echo()
    print_load(assessors, proposals, leads, cos)
    if output:
        write_assignments(output, proposals, leads, cos)
        click.echo(f"\nWrote {output}")


@cli.command()
@proposals_argument
@co_assessors_option
@click.argument("preassign_csv", type=click.Path(dir_okay=False, path_type=Path))
def prefill(proposals_csv: Path, n_co: int, preassign_csv: Path) -> None:
    """Interactively build or edit the Pre-assignment file PREASSIGN_CSV."""
    assessors, proposals = read_proposals(proposals_csv)
    if preassign_csv.exists():
        leads, cos = read_preassignments(preassign_csv, proposals)
        click.echo(f"Loaded existing Pre-assignments from {preassign_csv}")
    else:
        leads, cos = [None] * len(proposals), [[] for _ in proposals]

    while True:
        click.echo()
        for i, p in enumerate(proposals, start=1):
            current = _describe(leads[i - 1], cos[i - 1])
            click.echo(f"{i:>3}. {_truncate(p.title, 60)}{f'  [{current}]' if current else ''}")
        choice = click.prompt(
            "\nProposal number to edit (blank to save and quit)", default="", show_default=False
        )
        if not choice.strip():
            break
        if not choice.isdigit() or not 1 <= int(choice) <= len(proposals):
            click.secho("Not a valid proposal number", fg="red")
            continue
        i = int(choice) - 1
        leads[i], cos[i] = _edit_proposal(proposals[i], assessors, n_co)

    write_assignments(preassign_csv, proposals, leads, cos)
    click.echo(f"Wrote {preassign_csv}")


def _describe(lead: str | None, cos: list[str]) -> str:
    parts = ([f"Lead: {lead}"] if lead else []) + ([f"Co: {', '.join(cos)}"] if cos else [])
    return "; ".join(parts)


def _edit_proposal(
    proposal: logic.Proposal, assessors: list[str], n_co: int
) -> tuple[str | None, list[str]]:
    """Prompt for one proposal's roles, offering only eligible assessors."""
    click.secho(f"\n{proposal.title}", bold=True)
    available = logic.eligible_assessors(proposal, assessors)
    ineligible = [a for a in assessors if a not in available]
    if ineligible:
        click.echo(f"Ineligible: {', '.join(ineligible)}")

    lead = _pick(available, "Lead Assessor")
    remaining = [a for a in available if a != lead]
    cos: list[str] = []
    for k in range(n_co):
        co = _pick(remaining, f"Co-Assessor {k + 1}")
        if co is None:
            break
        cos.append(co)
        remaining.remove(co)
    return lead, cos


def _pick(options: list[str], role: str) -> str | None:
    if not options:
        click.echo(f"No eligible assessors left for {role}")
        return None
    for k, name in enumerate(options, start=1):
        click.echo(f"  {k}. {name}")
    while True:
        raw = click.prompt(
            f"{role} (blank = leave to the algorithm)", default="", show_default=False
        ).strip()
        if not raw:
            return None
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        click.secho("Choose a number from the list", fg="red")


if __name__ == "__main__":
    cli()
