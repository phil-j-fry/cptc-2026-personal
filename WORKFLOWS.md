# Workflows (tentative)

Nothing here is settled. Roles haven't been decided, so this file assumes only two:

- **Everyone:** everyone tests, takes notes (optionally in `tools/notebook.py`, if built) and writes up their own findings.
- **The report writer:** one person (who is TBD) who assembles and submits the report.

Every other job (final severity calls, the findings index, incident reports, status updates, injects, talking to Operations) has **no owner yet**. Those jobs are marked "owner TBD" wherever they appear and are listed in the open question "Who owns which team jobs?" in `OPEN-ITEMS.md`.

The commands and file names here match `README.md` (working copy) and `templates/README.md` (naming, markers). If they ever disagree, fix this file.

## 1. Everyone (all day)

1. **Set up (kickoff).** Make your working copy and folders (`README.md` → Working copy), then start every terminal with `~/cptc-work/scripts/logged-shell.sh <yourname>` from inside `~/cptc-work`. Without a name, every box's logs are named `kali`.
2. **Work from the checklist** for what you're testing (`checklists/10`, `20`, `30`, `60`). Record hosts and credentials in your tracker rows (`templates/tracker/README.md`).
3. **Log every change you make** on a client system (an account created, a password changed, a file dropped, a service touched) in `created-accounts-and-artifacts.csv` at the moment you make it. The report's Appendix F and the cleanup list come from this file.
4. **Tell the team before touching OT.** Before sending any traffic to suspected ride or OT systems, say so (`checklists/30`).
5. **Stop and tell the team** if anything goes down, an account locks, an unexpected host appears or a sensitive system responds (R10). Who files the incident report, and how fast, is TBD (open questions).
6. **Found something?** Take an ID the moment you find it. How IDs are allocated is **TBD** (R6; blocked by the open question "Is shared storage or a shared document provided?" in `OPEN-ITEMS.md`).
7. **Create the file:** copy `templates/finding.md` (or a matching `findings-library/` entry; whether unwritten library entries are usable on the day is a TODO) to `~/cptc-work/findings/F-NNN-short-name.md`. (`notebook.py` does this if it's built.)
8. **Fill it in:** every `[[FIELD]]`, every `[[CHOOSE]]`, delete every `[[NOTE]]` once you've followed it. Reproduction steps need an exact command and an `Expected:` line each (R7).
9. **Evidence:** save screenshots as `evidence/F-NNN-01.png` (`checklists/40`). Redact secrets to first and last characters.
10. **Hand over** to the report writer (rsync or zip, `README.md` → Working copy). You keep editing your own file when the report writer asks for changes; the next pull brings them across. Once a finding has been pasted into `report.md`, any further change is made there by the report writer (R18), so tell them about it.
11. **Clean up** what you created (from your `created-accounts-and-artifacts.csv` rows) and mark each row `cleaned_up`. When this happens is TBD; it must be before access to the environment ends (open question).

## 2. The report writer (from the midpoint)

1. **At the midpoint,** copy the template once: `cp ~/cptc-work/templates/report.md ~/cptc-work/report.md`.
2. **Pull teammates' files:** re-run the rsync lines (or unzip) into `incoming/<name>/` (`README.md`). That includes each person's `tracker/`: merge their created-accounts and attack-path rows by hand for Appendix F and the Attack Path section.
3. **Run `python3 tools/compile.py`** (if built). It writes `build/findings-summary.md` (the counts and findings table), `build/findings-combined.md` (all findings, severity order), `build/interactions-timeline.md` (the Section 7 timeline, built from the `IR-`, `SU-` and `INJ-` files) and `build/qa-report.txt`. Draft mode warns but never fails. Without the tool: paste findings by hand, ordered by severity.
4. **Paste into `report.md`:** summary table into Section 3, timeline into Section 7, counts into the Executive Summary (these are regenerated tables, safe to replace each time). Paste each **finding** into Section 5 **once**, when it shows READY, and make any later changes in `report.md` (R18): re-pasting a finding would overwrite those edits. If the author changes a finding after it was pasted, update that finding by hand in `report.md`.
5. **Fix what the QA report lists:** ask the author to fix findings not yet pasted; fix pasted ones in `report.md`. Repeat steps 2–4 as new findings arrive.
6. **Final 90 minutes:** run `python3 tools/compile.py --final` (if built). Then do the manual pass in `checklists/50-report-qa.md` (with a second person), export (format and method TBD, open questions), and submit (method TBD, open question).
7. **After submitting,** nothing from the engagement goes into the repo (R3).
