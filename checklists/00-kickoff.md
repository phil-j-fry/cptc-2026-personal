# Kickoff Checklist (first 30 minutes)

- [ ] Read the **Scope of Work** and **Rules of Engagement** aloud to the whole team
- [ ] Write the **in-scope ranges** and the **explicit exclusions** on the whiteboard
- [ ] Note any ROE limits on: password spraying, poisoning/relay, DoS-prone tests, social engineering, OT/ride systems, data exfiltration
- [ ] Record the client contacts and how to reach the Operations Team
- [ ] Record the deliverable deadlines and set timers for each one
- [ ] Assign roles (see README) and the first-hour targets
- [ ] Everyone makes their working copy **first** (the guarded command in the README; it refuses if `~/cptc-work` already exists) and works only inside it. Do this before any logged shell, so logs and scan output never land in the git clone.
- [ ] Agree how finding IDs are allocated and write it on the whiteboard (**TBD**, R6: a shared doc, or per-person blocks such as F-001 to F-020, F-021 to F-040; blocked by the open question "Is shared storage or a shared document provided?" in `OPEN-ITEMS.md`)
- [ ] Everyone runs `~/cptc-work/scripts/logged-shell.sh <name>` from inside `~/cptc-work` (or adds the auto-start block to `~/.zshrc`), starts a PowerShell transcript on the Windows box, and checks the system clock. Both are in `scripts/logged-shell.md`.
- [ ] Confirm with Operations how files may move between our boxes (shared storage, `scp`/`rsync`, or manual export); decide the method and who the report writer pulls from
- [ ] If using `rsync`/`scp`: change the default `kali` password, then `sudo systemctl start ssh`
- [ ] Create an empty `~/cptc-work/ot-hosts.txt` (scans use `--excludefile ~/cptc-work/ot-hosts.txt`). Whoever identifies an OT host says so aloud and writes it on the whiteboard, and everyone appends it to their own file. No tool shares this file between machines (**TBD:** blocked by the open question "Is shared storage or a shared document provided?" in `OPEN-ITEMS.md`).
- [ ] Copy `templates/tracker/` to `~/cptc-work/tracker/`. How the team shares it is **TBD** (blocked by the open question "Is shared storage or a shared document provided?" in `OPEN-ITEMS.md`); see `templates/tracker/README.md`.
- [ ] Agree on the "stop and tell the team" triggers: anything goes down, an account locks, an unexpected host shows up, or a sensitive system responds
- [ ] **If unsure whether a target is in scope, ask Operations before touching it.**

## Midpoint (halfway through the event)
- [ ] The report writer copies `templates/report.md` to `~/cptc-work/report.md` and starts assembling the report there
- [ ] Check `attack-path.csv`: if a path reaches a critical asset, write the chain finding (rule R9; owner TBD; see "Who owns which team jobs?" in `OPEN-ITEMS.md`)
- [ ] Executive summary draft v0
- [ ] Every finding so far has evidence and an owner
- [ ] Send a client status update (`templates/status-update.md`)

## Final 90 minutes
- [ ] No new exploitation. Writing only.
- [ ] If `tools/compile.py` is built: `python3 tools/compile.py --final`. It checks the Markdown report and every finding. The exported PDF/DOCX still needs the manual checks in the QA sheet.
- [ ] Severity consistency pass
- [ ] Remediation steps are specific and testable
- [ ] Spell check, and check that IDs match evidence filenames
- [ ] Run `checklists/50-report-qa.md` on the exported report before submitting
- [ ] Record cleanup status of anything left on systems
