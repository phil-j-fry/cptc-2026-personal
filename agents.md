# Agent rules for this repo

These rules apply to every agent session working in this repo (App Dev Manager, Task Planner, implementor, adversarial implementor, code reviewer). The user's word overrides anything here.

## Ground rules

1. **No deleting files** without the user's explicit consent.
   - Standing consent covers one case only: tests may create and delete their own files inside `tools/tests/.tmp/`.
2. **Stay inside the repo.** Never create, change or delete anything outside `/Users/pdemmert/Documents/edu/CPTC/cptc2026`. That includes temp files: tests use `tools/tests/.tmp/`, never `/tmp` or the OS temp folder.
3. **Disagreements get two rounds.** If two agents still disagree after two back-and-forths, stop and take the issue to App Dev Manager, who brings it to the user for a decision.
4. **`dev-tasks` note is read-only** for everyone except App Dev Manager and the Task Planner.
5. **No git:** no commits and no pushes. The user handles git.
6. **Build rules come from `tools/BUILD-SPEC.md`** plus the DECISIONS section of `dev-tasks`. Where they differ, DECISIONS wins.
   - Python 3.9, standard library only. Small, plainly named functions; comment the *why*.
   - Only change files outside `tools/` when a task names them.

## Workflow (one task at a time, in `dev-tasks` order)

1. **App Dev Manager** hands one task to the **implementor**.
2. The **implementor** writes the code and tests directly in `tools/` and runs `python3 -m unittest discover tools/tests`.
3. The **adversarial implementor** reviews the work. The implementor fixes it until they agree (rule 3 applies).
4. **At the end of each review chunk** (listed in `dev-tasks`), the implementor asks the **code reviewer** to review the whole chunk. The reviewer either requests changes or approves. The implementor applies any requested changes (rule 3 applies).
5. **App Dev Manager** confirms each task is done (tests pass, acceptance check met), then ticks its box in `dev-tasks`. Any issue that needs the user goes to the user through App Dev Manager.

## User checkpoints

Work pauses for the user's review at these milestones:

- **M1:** after compile Chunk 1 (test base, template edits, spec update, path safety). An early look at style.
- **M2:** CHECKPOINT `CP-02`, when `compile.py` is complete. Required by the spec; no notebook work starts before the user approves.
- **M3:** after notebook Chunk N5, when notebook features 1–4 (the never-cut core) are complete.
- **M4:** after the remaining notebook features, the docs and the Definition-of-done checks.
