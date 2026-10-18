# To-Do

Tasks, not questions. Open questions are in `OPEN-ITEMS.md`; the rules are in `CONVENTIONS.md`. Tick an item when it's done; delete the file's contents after the event, since nothing here is engagement material.

## Build and handoff
- [ ] Hand `tools/BUILD-SPEC.md` to a Claude Code build session. Build `compile.py` first.
- [ ] Review the code line by line (R4: we must be able to explain it).
- [ ] Update `README.md`'s layout table and the checklists to point at the tools once they exist (listed in the spec's Deliverables).

## Library
- [ ] Decide what happens to library entries that are still unwritten by game day. Right now the only way to tell an entry's state is the status column in `findings-library/README.md` (☐ / ◐ / ☑); the entry files themselves don't say. Options: delete unwritten entries before the lock, or make each entry carry its own status line.

## Meeting and team
- [ ] **Repo access request: send by Oct 23** (rulebook: at least two weeks before the event *start time*, so the morning of Oct 24 is the hard cutoff). Checked Oct 17: I have read-only access (`push: false`). Now the captain's job (me).
    - [ ] Ask the organizer: has a request already gone in this season, and where do requests go (the rulebook says "the Operations Team" but gives no address)?
    - [ ] Collect GitHub usernames from all six teammates.
    - [ ] Send from a school email with the institution name and every member's GitHub account name.
- [ ] Go through `OPEN-ITEMS.md` with the student coordinator (not competing; heavy semester, so bounded asks only).
- [ ] Review each rule in `CONVENTIONS.md` section 2 with the team and mark it Agreed or drop it.
- [x] Review the existing CCSF repo against this one (salvage pass done Oct 17: decision is to rewrite; see "Team repo rewrite").
- [ ] Settle roles (`README.md` → Roles) and how finding IDs are allocated (R6).
- [ ] Fill the `PREP_` markers in `checklists/40-evidence-and-logging.md` (screenshot theme and font) before Oct 30.

## Captain handoff (added Oct 17)
- [ ] One sitting with the coordinator (she was involved last year, so she can answer from memory): can the jump box / Kali reach GitHub during the event, and if not, how did past teams get tools in? Then whatever else in `OPEN-ITEMS.md` she remembers (boxes, network, injects, report format and submission, access cutoff), and whether she knows why only a command list of the playbooks went into the team repo.
- [ ] Settle lanes (Web Apps, Windows, Linux, Report Writing; 2 each, so everyone doubles up). Windows has one taker so far. Decide deliberately which lane is shared.
- [ ] Decide my own hands-on lane (Linux is my stronger side; Windows is the one I'd be learning).
- [ ] Write down this year's team goals: complete professional report; everyone owns at least one finding end to end; zero incidents; leave a repo next year's team can inherit.

## Team repo rewrite (public, locks Oct 30)
- [ ] Tag the current team repo state (e.g. `archive/pre-2026`) before replacing `main`.
- [ ] Salvage: merge `ICS/Readme.md` + `Scans/` into `checklists/30-ot-ics-safe.md`; keep last year's report (`report/template.zip`, 2025) as a reference; replace `exfil-tools-server.js` with documented one-liners (`python3 -m http.server`, `impacket-smbserver`). Archive the rest (`install.sh`, `setup-kali.sh`, `nmap-static.zip`, `app/`).
- [ ] Skim the 2025 report: its Section 6 headings show only DNS records. Were findings elsewhere, or did the team not get far?
- [ ] Build the new `main` from this repo's generic scaffolding (templates, checklists, findings library, scripts, tools).
- [ ] Move team-internal files (this `TODO.md`, `OPEN-ITEMS.md`, `notes/technique-map.md`, lanes, study tiers) to the team's existing Drive folder. Both repos are public.
- [ ] Playbooks on a branch in the team repo; merge by Oct 25.

## Windows playbooks (first track; template for the others)
- [ ] Me: AD primer (~1 hour: Kerberos, NTLM, LDAP, what makes the DC special, how privilege flows) before reviewing playbooks.
- [ ] Get the vulnerability checklist (CSV) and playbook files from Drive.
- [ ] Add a risk column with a legend: Safe / Noisy / Disruptive (captain approval every time) / Prohibited (per the RoE). Color-code it.
- [ ] ZeroLogon: change "Exploit" to verify-only unless the RoE explicitly allows it. Keep EternalBlue and PrintNightmare scan-only, visibly marked.
- [ ] Add "Evidence to capture" and "Finding link" to each playbook (most map to L01, L03, L04, L05, L06).
- [ ] Recover the 2022 AD notes from team-repo history (deleted in the Nov 2024 rewrite of `AD/README.md`): Responder, SMB relay with `ntlmrelayx`, mitm6, psexec/wmiexec/smbexec. Source material for the LLMNR/relay gap.
- [ ] Check gaps against the full list: BloodHound, AD CS (L12), spraying with lockout awareness, GPP/LAPS, DCSync, LLMNR/relay (L10).
- [ ] Playbooks reference checklist steps, not the other way around (keep `checklists/` generic).
- [ ] Mark the Drive copy as superseded once converted.

## Other tracks
- [ ] Web Apps: reorganize into the Windows format.
- [ ] Linux: write a playbook skeleton (none exists). Service exposure + local privesc, 10-15 entries; kernel exploits tagged Disruptive.
- [ ] OSINT: confirm the rules allow pre-competition recon (timing; passive only). I write a basics doc, then we review my writeup as a finding → pivot → test table with a confidence column.

## Study plan
- [ ] Re-key `notes/technique-map.md`: replace the week column with Tier (Must know / Recognize / Reference) + Order; add playbook #, tools, practice box, risk. Tools inherit the highest tier of any technique that uses them. Leave anything outside the playbooks unranked.
- [ ] Send the team the ordered study list (technique → practice box) as soon as the Windows tiers are set. Don't wait for the playbooks to be polished.

## Dry run and app (before the Oct 30 lock)
- [ ] Dry run: everyone works an HTB box, takes notes in the team format, and pushes at least one finding through `compile.py`.
- [ ] App helper: pops the Windows practice boxes using the playbooks and reports where they're wrong or confusing; writes findings in our template (HTB notes stay out of the public repo); reads `compile.py` at the function level.
- [ ] Half-page operator card for `compile.py` (how to run it, how to read the output, fallback: plain Markdown templates assembled by hand), after `compile.py` stabilizes.
- [ ] If time allows: look at `compile.py` size (429 lines vs. the spec's 200-250 guideline).

## Network and game-day logistics (added Oct 17)
Known: personal machines have public internet, no personal logins. Rulebook (Oct 2025): teams "may make changes to the content on their repository during Competition hours from the Competition Environment", so the competition boxes very likely reach GitHub. External collaboration tools (Google Drive etc.) and private Internet storage are banned unless officials provide them, so Drive is prep-only.
- [ ] Ask the organizer, in the same sitting: (1) can the Kali boxes reach GitHub (confirm)? (2) is Kali reached by SSH only, or does it have a desktop (RDP/VNC)? (3) can our team's boxes reach each other over SSH? (4) is the jump box SSH (port forwarding allowed), or a desktop/web portal? (5) do officials provide shared storage? (6) can we push to the repo from a competition box, given the no-personal-accounts rule?
- [ ] Add a 5-minute network check to `checklists/00-kickoff.md`: `git clone` first; `nc -zv <teammate-kali> 22`; then pick the collection method (rsync / jump-box hop / export zips) and how to view the notebook (Kali browser / `ssh -J ... -L 8000:127.0.0.1:8000` / Windows box). Note the Host-check gotcha: browse `http://127.0.0.1:<same port>`, not `localhost`.
- [ ] Optional, after answers (3) and (4): `pull.sh` (~15 lines) reading a `team.txt` of `name IP` filled in at kickoff, running the four rsync lines per person into `incoming/<name>/`. Use one SSH key from the report writer instead of shared passwords.
- [ ] Fix the README rules section: it paraphrases the repo rule as "changes may be made only from inside the competition environment"; the rulebook wording is permissive ("may make changes ... from the Competition Environment"), and the freeze covers only the week before the event.
- [ ] Fold the organizer's answers (already partly given) into `OPEN-ITEMS.md`, following that file's rule.

## Playbook publishing rules
- [ ] Each playbook: game-day content on top, a `## Practice` section at the bottom (HTB box, walkthrough link, example creds). Try it on the first playbook and keep it only if it reads well.
- [ ] Link walkthroughs, don't paste them. Retired HTB boxes only. One-line credit to the CCSF 2024 playbooks.

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
