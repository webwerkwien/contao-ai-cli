# contao-ai-cli — Development

This file is for coding agents working *on* this CLI, whatever the tool. It is
`AGENTS.md` so that tools reading that name find it; `CLAUDE.md` only imports it.

How to *use* the CLI against a site is in `GUIDE.md`. That file ships with the package
and is what `contao-ai-cli guide` prints; this one stays in the repository. Read both:
`GUIDE.md` is part of the product.

---

## Working on this CLI

```bash
python -m pytest -q        # the gate — must be green
```

There is no linter and no type checker configured; the suite is the whole gate.

**Checking what the package contains:** delete `build/` first. `setup.py` builds in the
source tree, and whatever a previous build left in `build/lib` is packaged as it is. Once
the test suite still showed up in the wheel after it had been excluded; a fresh
clone (what `pipx install git+…` and `self-update` use) was never affected.

Healthy output has this shape:

```
… passed, … skipped in …s
```

The counts are deliberately not written down — they change with every commit.
What must hold is that nothing failed.

**Run it before reporting any task complete, and paste the output.**

**For a bug fix, write the failing test first.** Reproduce the bug as a test, run
it, confirm it fails for the reason you expect, and commit that test before
touching the implementation. Do not edit test files while making the fix — a test
that existed before the fix, and could not be rewritten, is the proof.

### Two things that go wrong here

**1. `GUIDE.md` is part of the product, and it drifts.**

`test_docs_match_cli.py` pins README and `GUIDE.md` to the real command tree —
name, existence, option spelling — because both once promised commands that did
not exist. **Its own docstring names its boundary:** it does not check what a
command *answers*. In v0.12.0 `ext run` changed its return value and then
gained a `hint` field; the file stayed green both times while the guide said
nothing about either.

> A green `docs match cli` is a statement about the command tree only. If what a
> caller sees has changed, no test covers it: change `GUIDE.md` in the same commit.

Development notes belong here, not in `GUIDE.md`: everything in `GUIDE.md` reaches
every installation.

**2. A measurement belongs to the binary and the environment it was taken in.**

On Windows the code picks `C:\Windows\System32\OpenSSH\ssh.exe` explicitly. A
reproduction typed into Git Bash runs MSYS-ssh instead and answers differently —
close enough to look like a result, different enough to be the wrong one. Drive
the real code path (`ContaoBackend.__new__` plus `_ssh_args()`) and set the same
environment the code sets.

### Convention

- **Agent-neutral.** `AGENTS.md` is the one development guide for every coding agent; `CLAUDE.md`
  only imports it. Nothing here may depend on one coding agent: no agent-specific instructions,
  paths or file names in either guide, the tests or the code — the `CLAUDE.md` shim that
  only imports this file is the one exception.
- **No internals in the CHANGELOG** — nor in the GitHub release notes, which copy it: no names, no review or
  acceptance tags, no servers or hosts, no test data, no keys or key IDs. Only what changes for the people using
  the CLI.
  Removing internals is not announced either: nothing like "no longer refers to" or "removed internal
  references" — that says there were some, and the diff between the tags shows them. Done with a regular
  release, it goes unmentioned; on its own, the entry reads "Overhaul of code comments and the agent guide."
- **Every tracked file is public, and English.** Code, comments, tests, test data, docs and commit messages
  carry no internals either: no names of people or clients, no servers, hosts or paths on them, no session
  names, no data from real sites (field names, page IDs, aliases, e-mail addresses — use neutral examples
  and `example.com`), no review or acceptance tags, no references to private notes, plans or project files.
  A reason belongs in the comment as a plain statement, not as a pointer elsewhere. Comments and docs are
  English even where a file still has German ones; German stays only where the content is German by nature
  (Contao's German messages as test data, German sample text for editors).
- **What ships:** the package carries `GUIDE.md` (`setup.py` copies it in, `MANIFEST.in`), not this file.

Every scanning test needs a counter and at least one known non-match. A search
that finds nothing passes exactly like one that finds everything.
