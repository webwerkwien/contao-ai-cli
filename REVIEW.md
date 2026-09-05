# Review instructions

How to review a change in this repository. Findings do not approve or block on
their own — a human decides.

## Passes

Run three passes and tag every finding with the pass it came from.

**Bugs** — logic errors, broken edge cases, subtle regressions. Pay particular
attention to anything that changes what a command *answers*, since the doc tests
do not cover that.

**Security** — a secret reaching a command line or a process list, a host key
accepted without the operator seeing it, an SSH argument that could be read as an
option, output that leaks credentials or personal data, a write path that avoids
the audit trail.

**Compliance** — does the change do what its commit message and CHANGELOG entry
say it does, no more and no less? Undeclared behaviour changes belong here.

## What Important means here

Reserve **Important** for findings that would break behaviour, leak data, or
mislead a calling agent. Everything else is a nit.

Specifically Important, because each has happened:

- **A changed return value or a new field, without a matching change to
  `CLAUDE.md`.** The doc tests stay green through this — they check the command
  tree, not the answer. This slipped through twice on 2026-09-01.
- A secret passed as a command-line argument where stdin is available.
- A measurement or reproduction taken in a different environment than the code
  runs in — Git Bash's ssh is not the ssh this CLI invokes.
- A verification claim without the command output that backs it.
- A check that cannot fail under the conditions it runs in.
- A scanning test without a counter, or without a known non-match beside it.

## Cap the nits

At most five nits per review; summarise the rest as a count.

## Do not report

- Style and naming, unless it contradicts a convention in `CLAUDE.md`.
- Missing type hints or lint findings. Neither a type checker nor a linter is
  configured here; proposing to add one is a separate change, not a review
  comment on someone else's diff.
- Anything the test suite already enforces — if such a finding appears, the suite
  was not run, and *that* is the finding.

## On test changes

Treat any edit to an existing test as a finding worth a look. Weakening a check
to make a fix pass is the failure mode this section exists for. A deleted or
loosened assertion needs a reason in the commit message.

`test_docs_match_cli.py` is the one to watch: it is easier to relax the test than
to update the guide, and the guide is what a calling agent reasons from.
