# Open Questions and Unconfirmed Items

Everything we still need answered, in one list. Rules and conventions are in `CONVENTIONS.md`; tasks are in `TODO.md`. When a question is answered, move the answer into the right rule or convention, update every item in the table below that it was blocking, then delete the question.

## Open questions

Gathered from planning so far. One list: who answers each one gets worked out when the team meets. Move an item into `CONVENTIONS.md` once it's answered.

- [ ] **How does this work fit with the existing CCSF repo?** What gets adopted, merged or dropped? (Everything here is a proposal until then.)
- [ ] **Repo access:** has the access request gone in (it's due 14 days before the event)? Are all current members listed, and graduated members removed?
- [ ] **Roles, and who owns which team jobs?** So far we assume only "everyone" and "the report writer" (`WORKFLOWS.md`). Jobs with no owner yet (each marked "owner TBD" where it appears): final severity calls (R8), checking reproduction steps before a finding goes in (R7), the chain finding (R9), the findings index (R17), incident reports (R10), talking to Operations and the client, status updates, injects, choosing the QA reader (R15), and what the team captain facilitates. (`README.md` → Roles is still blank.)
- [ ] **Our in-character firm name and branding** (`[[FIRM_NAME]]`, cover page, logo).
- [ ] **Review each rule in section 2**, especially R1, R2 and R9.
- [ ] **What report format is submitted** (PDF, DOCX, either)? Is there a page limit or required sections? Is Word required? Nothing we know of says it will be used (the only hints: last season's repo had a 2022 `.docx` template, and some finalist notes are `.docx`), so we plan on Markdown and avoid Word for now. **Why we ask:** if Word is used, `tools/compile.py` can't check inside the .docx, and Word leaves its own kinds of leftovers (broken cross-references showing "Error! Bookmark not defined", stray comment text). If Word is used, add checks for those leftovers to the exported-file search in `checklists/50-report-qa.md` (they only exist inside the exported file, which `compile.py` can't read). Not added until this is answered.
- [ ] **What tool builds the final report?** Is there a designed template? Last season's repo had a 2022 `.docx` template. This decides how our Markdown becomes the final document.
- [ ] **What was on the competition boxes?** Word or LibreOffice, pandoc, Python 3, Burp? Was there internet access (to clone the repo from GitHub, or install tools)?
- [ ] **Network layout:** could teammates' boxes reach each other? Was there one Windows box per person or a shared one? How did last year's team move files?
- [ ] **Is there a pre-event proposal or RFP deliverable for regionals?** The rulebook scores "communication during the proposal process."
- [ ] **Injects:** during CPTC the fictional client sends requests mid-event ("can you look at this new server?", "write us a memo about X"), and responses are scored. How are they delivered and answered at regionals? **How many injects came in at regionals, and were there scheduled mid-event deliverables** (status updates, interim findings) with fixed due times? This decides how much of the day goes to client communication, and whether R13/R14 need fixed times.
- [ ] **Regionals presentation:** is there one, how long is it, and who presents? The rulebook mentions regional group presentations.
- [ ] **Did every box log in as the same user** (e.g. `kali`) with default passwords?
- [ ] **Is shared storage or a shared document provided for the team?** Four things wait on the answer: (1) **finding ID allocation** (R6): with a shared doc, anyone could take the next number themselves; without one, per-person ID blocks (and how big each block is); (2) **the tracker** (`templates/tracker/README.md`): who can see whose rows; (3) **`ot-hosts.txt`**: how the whole team sees the do-not-touch list (until then: announce aloud, write it on the whiteboard, each person appends to their own `~/cptc-work/ot-hosts.txt`); (4) **credentials**: one person's cracked password is invisible to the others unless the credentials list is shared, which risks retries and lockouts.
- [ ] **How may teammates move files to each other, and to the report writer?** Specifically: (a) may we use `scp`/`rsync` between our own team's Kali boxes (our reading of the file-sharing rule says yes; we want explicit confirmation)? (b) Does RDP drive mapping work? (c) Does the RDP clipboard work for pasting text? Why it matters: `tools/notebook.py` has two export options. Option (a) is a zip file, which needs one of the transfer methods above. Option (b) is a single combined Markdown file pasted through the RDP clipboard, and only matters if no file transfer is possible. It stays in the build spec as the lowest priority, and the answer decides whether it is worth building.
- [ ] **What are the rules for OT / ride systems?** Is there live ride access at all, or only a simulated or read-only environment? Are any write operations to controllers ever allowed, and does that need written client permission? Our checklist and library text assume no writes and written OK for any state change (R11); that is our own policy and unconfirmed. **Waiting on this answer (all marked "Unconfirmed"):** R11 in section 2; the note at the top of `checklists/30-ot-ics-safe.md`; the Severity notes in `findings-library/L18-ot-network-segmentation.md` and `L19-unauthenticated-industrial-protocol.md`.
- [ ] **Does the "explain your code" rule cover AI-assisted code?** Our tools are AI-assisted and reviewed line by line by a team member; we want to confirm that satisfies the rulebook.
- [ ] **Which AI systems, cloud assets and social-engineering targets are in scope,** and is automated prompting of AI systems allowed?
- [ ] **Screenshot standard:** terminal theme and font size (`checklists/40-evidence-and-logging.md`). Proposed: light background, monospace, 14pt or larger.
- [ ] **zsh auto-start block** or manual `logged-shell.sh` per terminal? Proposed: auto-start, once tested.
- [ ] **Screenshots and export:** how do screenshots end up as pictures in the final report, and what turns our Markdown into the submitted file? Background: a finding refers to its screenshot as plain text (`` `evidence/F-001-01.png` ``), which shows as a filename, not a picture; Markdown shows a picture only as `![caption](path)`. Converting Markdown to PDF or Word needs a tool (pandoc, Word, LibreOffice), and we don't know what's on the boxes. Depends on the report-format and competition-box questions above. Once known, decide whether to change `templates/finding.md` and do a practice export.
- [ ] **Does access to the environment end before the report deadline?** Some regionals cut off access mid-afternoon and give teams until midnight to write the report (CPTC West 2023, per its published schedule). If ours does, testing must stop and everything needed (evidence, logs, tracker rows) must be pulled off the boxes before the cutoff, and cleanup moves earlier.
- [ ] **How is the report submitted** (portal, upload, file name), and can we resubmit (for example a first version an hour before the deadline, then a final)?
- [ ] **Does the client expect status updates, and how often?** `templates/status-update.md` and R13 assume they exist; that's an assumption.
- [ ] **What do the rules require for incident reports, and how fast?** The repo currently assumes: tell Operations immediately, written report within the hour. The rulebook says incomplete, vague or untimely reports earn nothing, but we haven't confirmed a deadline.
- [ ] **Is there a kickoff interaction with the client** (for example confirming scope, IP ranges, exclusions and an emergency contact in writing)? Common in real pentests; unknown whether CPTC expects or scores it.

## Unconfirmed items and what blocks them

Every item tagged "Unconfirmed" or "TBD" in the repo is listed here with the open question above whose answer settles it. When a question is answered, update each item below, then remove its tag.

| Item (where it appears) | Blocked by this question |
|---|---|
| R11 OT limits (no writes, written client OK for state changes): `CONVENTIONS.md` R11; top of `checklists/30-ot-ics-safe.md`; Severity notes in L18 and L19 | "What are the rules for OT / ride systems?" |
| R6 finding ID allocation (shared doc or per-person blocks): R6; `README.md` workflow step 3; `templates/README.md` workflow step 1; `WORKFLOWS.md` step 6; `checklists/00` (ID line); `checklists/40` (ID line); `tools/BUILD-SPEC.md` (context, new-file NNN) | "Is shared storage or a shared document provided?" |
| R17 / tracker sharing method TBD: R17; `templates/README.md` tracker row; `templates/tracker/README.md`; `checklists/00` (tracker line) | "Is shared storage or a shared document provided?" |
| `ot-hosts.txt` sharing (announce aloud, whiteboard, each person appends): `checklists/00`; `checklists/30` ("The port list is a safety net") | "Is shared storage or a shared document provided?" |
| Notebook export option (b), the pasted combined Markdown file: `tools/BUILD-SPEC.md` | "How may teammates move files…?" |
| `scp`/`rsync` between our boxes: `README.md` → "Rules check" | "How may teammates move files…?" |
| Export format and method: `WORKFLOWS.md` report writer step 7 | "What report format is submitted?" |
| AI-assisted code: R4; the "Where did this come from?" answer in `scripts/logged-shell.md` | "Does the 'explain your code' rule cover AI-assisted code?" |
| The `kali@` login in the rsync lines: `README.md` → option 2 | "Did every box log in as the same user?" |
| Event environment assumed by the tools (own Kali + Windows per tester, Python 3.9+, no internet): `tools/BUILD-SPEC.md` → Context | "What was on the competition boxes?" and "Network layout" |
| Whether LibreOffice Calc is available for the tracker: `templates/tracker/README.md` | "What was on the competition boxes?" |
| Team jobs with no owner yet: R7, R8, R9, R10, R17; `templates/README.md` (which-template table); `templates/severity-guide.md` (consistency rule); `checklists/00`, `40` (incident lines) | "Roles, and who owns which team jobs?" |
| Incident report timing: R10; `README.md` workflow step 5; `templates/README.md` (incident row); `WORKFLOWS.md` step 5 | "What do the rules require for incident reports, and how fast?" |
| Cleanup timing: `WORKFLOWS.md` step 11 | "Does access to the environment end before the report deadline?" |
