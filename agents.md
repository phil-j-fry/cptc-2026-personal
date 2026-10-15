# Agent rules for this repo

These rules apply to every agent session working in this repo (App Dev Manager, Task Planner, implementor, adversarial implementor, code reviewer). The user's word overrides anything here.

## Ground rules

1. **No deleting files** without the user's explicit consent.
   - Standing consent covers one case only: tests may create and delete their own files inside `tools/tests/.tmp/`.
2. **Stay inside the repo.** Never create, change or delete anything outside `/Users/pdemmert/Documents/edu/CPTC/cptc2026`. That includes temp files: tests use `tools/tests/.tmp/`, never `/tmp` or the OS temp folder.
3. **Disagreements get two rounds.** If two agents still disagree after two back-and-forths, stop and take the issue to App Dev Manager, who brings it to the user for a decision.
4. **`dev-tasks` note is read-only** for everyone except App Dev Manager and the Task Planner.
5. **No git commits or pushes unless the user asks.** `git commit` and `git push` are reserved for the user (the project owner). No agent or session runs them on its own, even at the end of a task or chunk.
6. **Build rules come from `tools/BUILD-SPEC.md`** plus the DECISIONS section of `dev-tasks`. Where they differ, DECISIONS wins.
   - Python 3.9, standard library only. Small, plainly named functions; comment the *why*.
   - Only change files outside `tools/` when a task names them.

## Workflow (one task at a time, in `dev-tasks` order)

1. **App Dev Manager** hands one task to the **implementor**.
2. The **implementor** writes the code and tests directly in `tools/` and runs `python3 -m unittest discover tools/tests`.
3. The **adversarial implementor** reviews the work. The implementor fixes it until they agree (rule 3 applies).
4. **At the end of each review chunk** (listed in `dev-tasks`), the implementor asks the **code reviewer** to review the whole chunk. The reviewer either requests changes or approves. The implementor applies any requested changes (rule 3 applies).
   - **Breakdown doc:** at the end of each chunk, the implementor also updates `tools/<tool>-breakdown.md` (`compile-breakdown.md`, and from Chunk N1 `notebook-breakdown.md`). The code reviewer checks it against the code before approving.
   - The breakdown doc has four sections: the tool's code; the test helpers in `tests/support.py` (the notebook doc links to the compile doc's helper section rather than repeating it); the tests; and related edits outside `tools/`.
   - Each entry gives the function name with its line range, a short description, and "If Operations asks, a student can say: …".
5. **App Dev Manager** confirms each task is done (tests pass, acceptance check met), then ticks its box in `dev-tasks`. Any issue that needs the user goes to the user through App Dev Manager.
6. **Git belongs to the user.** No agent or session runs `git commit` or `git push` unless the user asks for it (ground rule 5). A finished task or chunk is left uncommitted in the working tree for the user.

## User review stops

**Work stops for the user at the end of every review chunk** (one feature: related functions plus their tests, roughly 150–250 lines). The chunks are listed in `dev-tasks`.

1. The chunk must be finished first: every task AGREED, the code reviewer has APPROVED, the breakdown doc is updated, and the tests pass.
2. **feature-review** walks the user through the chunk:
   - **the tool's code:** line by line, in small blocks
   - **the tests:** summarized ("these tests prove X"), with detail only when the user asks
3. feature-review sends App Dev Manager one numbered change list. The change requests go through the normal workflow above.
4. The user commits the chunk (one commit per stop, conventional style: `feat:`, `test:`, `docs:`). Agents never commit.
5. **No building ahead:** no work on the next chunk starts until the user says go.

### Milestones

Some stops are also milestones:

- **M1:** compile Chunk 1. Done.
- **M2:** `CP-02`, when `compile.py` is complete. Required by the spec; no notebook work starts before the user approves.
- **M3:** after notebook features 1–4 (the never-cut core) are complete.
- **M4:** after the remaining notebook features, the docs and the Definition-of-done checks.

### User edits

When the user is editing a file themselves (e.g. rewriting the comments in `compile.py`), no agent touches that file until the user hands it back.
