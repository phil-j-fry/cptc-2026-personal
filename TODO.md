# To-Do

Tasks, not questions. Open questions are in `OPEN-ITEMS.md`; the rules are in `CONVENTIONS.md`. Tick an item when it's done; delete the file's contents after the event, since nothing here is engagement material.

## Build and handoff
- [ ] Hand `tools/BUILD-SPEC.md` to a Claude Code build session. Build `compile.py` first.
- [ ] Review the code line by line (R4: we must be able to explain it).
- [ ] Update `README.md`'s layout table and the checklists to point at the tools once they exist (listed in the spec's Deliverables).

## Library
- [ ] Decide what happens to library entries that are still unwritten by game day. Right now the only way to tell an entry's state is the status column in `findings-library/README.md` (☐ / ◐ / ☑); the entry files themselves don't say. Options: delete unwritten entries before the lock, or make each entry carry its own status line.

## Meeting and team
- [ ] **Repo access request by Oct 24** (due 14 days before the Nov 7 event): confirm with the captain it's been sent, from a school email, with the school name and every member's account.
- [ ] Meet the captain and coach assistant with `OPEN-ITEMS.md`.
- [ ] Review each rule in `CONVENTIONS.md` section 2 with the team and mark it Agreed or drop it.
- [ ] Review the existing CCSF repo against this one (what to adopt, merge or drop).
- [ ] Settle roles (`README.md` → Roles) and how finding IDs are allocated (R6).
- [ ] Fill the `PREP_` markers in `checklists/40-evidence-and-logging.md` (screenshot theme and font) before Oct 30.

## Testing (before the Oct 30 lock)
- [ ] Run `scripts/logged-shell.sh` on Kali, including a remote session and an empty-Enter check.
- [ ] Test the zsh auto-start block and the PowerShell transcript lines. Neither has been tested yet.
- [ ] Spot-check the OT brittle-port list in `checklists/30-ot-ics-safe.md`.
- [ ] Review and run `tools/compile.py` when it's built, and `tools/notebook.py` if it is (including the token check and a `<script>` in a log file).
- [ ] Print every file in `checklists/`.

## Facts to verify
- [ ] Rulebook: an October 2025 revision is cited; confirm nothing changed for 2026.
- [ ] "UC Irvine (CPTC11 champion)" wherever it appears in notes or the README.
- [ ] CPTC10 described as "most recent": confirm.
- [ ] The `globalcptc/report_examples/*/presentation/` path.
- [ ] CWE fit: L11 (CWE-262) and L12 (CWE-295) look like loose matches.
- [ ] Counts quoted from our CPTC10 report analysis ("10 of 12 reports" in R7 and `scripts/logged-shell.md`; "two finalists mixed CVSS versions" and the calibration table in `templates/severity-guide.md`; "11 of 12 … 8 to 9" in `checklists/60`; source counts in `notes/technique-map.md`): re-check against the analysis before treating them as fact.
- [ ] L19's ATT&CK ID: the library uses ICS T0855, `notes/technique-map.md` lists T0846. Pick one.

## Housekeeping
- [ ] Keep `_backup-original-2026-10-12/` out of the team repo, and delete it once the merged files are accepted.
- [ ] Delete or archive `tools/BUILD-SPEC.md` after the tools are built, if the team prefers.
