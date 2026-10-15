# Team Conventions and Rules

This is the one page that collects how we work. Open questions and unconfirmed items are in `OPEN-ITEMS.md`; tasks are in `TODO.md`. Each entry links to the document that has the detail.

**Status:** everything below is **Proposed** until the captain and team review it. "(Phil ✓)" marks items Phil has already agreed to. Change an entry's status to **Agreed** once the team accepts it, or delete the entry if the team drops it.

## 1. Competition rules (from the official rulebook)

These aren't ours to change. Summary and source: `README.md` → "Rules that govern this repo". Re-check the [current rulebook](https://cp.tc/docs/cptc-rules.pdf) before the event.

- The repo is public, holds only pre-staged scripts and code, and is frozen during the 7 days before the event.
- Teams "may be asked to demonstrate or explain their pre-written scripts or code during the event."
- No *external* private storage or collaboration tools unless officials provide them, and no "peer to peer or distributed file sharing clients or servers" on competition networks.
- Incident reports: a thorough, timely report may reduce the penalty. Incomplete, vague or late ones earn nothing.
- No coach commits. Printed materials are allowed.

## 2. Team rules

| # | Rule | Why | Documented in | Status |
|---|---|---|---|---|
| R1 | **Pull only.** During the event we clone or pull the repo and never push engagement material. If a tool fix must be pushed, one designated person does it, and the commit contains code only. | The repo is public and every change is timestamped | This file | Proposed (Phil ✓) |
| R2 | **Work in the working copy** `~/cptc-work`, a plain copy with no `.git`. | Nothing from the engagement can be committed, even by accident | `README.md` → Working copy; `checklists/00-kickoff.md` | Proposed |
| R3 | **Nothing from the engagement ever goes in the repo:** client data, credentials, logs, findings, or environment details. That includes after regionals. | Public repo; the rulebook bars disclosure until finals conclude | `README.md` → Rules | Proposed |
| R4 | **Explain it or it doesn't go in.** Every script or tool must be explainable line by line, written by us (**Unconfirmed** whether AI-assisted code counts; blocked by the open question "Does the 'explain your code' rule cover AI-assisted code?" in `OPEN-ITEMS.md`), standard library only, with no copied code we don't understand. | The rulebook's "explain your code" clause | `scripts/README.md`; `tools/BUILD-SPEC.md` | Proposed (Phil ✓) |
| R5 | **Every terminal is logged:** `logged-shell.sh` (or the zsh auto-start), plus a PowerShell transcript on Windows. | Evidence, incident reports, answering the client | `scripts/logged-shell.md`; `checklists/00`, `40` | Proposed |
| R6 | **Every finding gets an ID the moment it's found.** How IDs are allocated is **TBD** (blocked by the open question "Is shared storage or a shared document provided?" in `OPEN-ITEMS.md`). The two options so far: (a) a shared doc where anyone takes the next number; (b) per-person blocks handed out at kickoff (e.g. F-001–F-020, F-021–F-040). | No collisions | `README.md` → Workflow; `templates/README.md` | Proposed (Phil ✓) |
| R7 | **The reproduction gate:** a finding without numbered steps, exact commands and expected results is sent back before it goes in the report (who checks: owner TBD; see "Who owns which team jobs?" in `OPEN-ITEMS.md`). | Judges' top criticism (10 of 12 CPTC10 reports) | `templates/finding.md`; `checklists/50-report-qa.md` | Proposed |
| R8 | **Severity:** one person makes the final call so ratings are consistent (owner TBD; see "Who owns which team jobs?" in `OPEN-ITEMS.md`); CVSS 3.1 only; rate what was demonstrated; one-line rationale per finding. | Consistency; CPTC10 rating spreads ran from Medium to Critical for the same issue | `templates/severity-guide.md` | Proposed (Phil ✓ on CVSS 3.1) |
| R9 | **Rate each finding on its own.** A combined path gets one extra chain finding (owner TBD; see "Who owns which team jobs?" in `OPEN-ITEMS.md`); choke points set remediation priority, not severity. | Avoids inflating every link | `templates/severity-guide.md` | Proposed (Phil ✓) |
| R10 | **Stop and tell the team** if anything goes down, an account locks, an unexpected host appears, or a sensitive system responds. An incident report follows (who files it: owner TBD; see "Who owns which team jobs?" in `OPEN-ITEMS.md`; how fast: **TBD**, see the open question on incident reports). | Penalty reduction requires speed | `checklists/00-kickoff.md`; `templates/incident-report.md` | Proposed |
| R11 | **OT safety:** no writes, no aggressive scans; brittle ports excluded from every broad scan; known OT hosts go in `ot-hosts.txt`. | Theme-park rides are safety-critical | `checklists/30-ot-ics-safe.md` | Proposed. **Unconfirmed** (our own safety limits, not rulebook rules; blocked by the OT question in `OPEN-ITEMS.md`) |
| R12 | **If unsure whether something is in scope, ask Operations before touching it.** | ROE violations cost points | `checklists/00-kickoff.md` | Proposed |
| R13 | **Notify the client of criticals during the event** with a status update; don't hold them for the report. | Client communication is scored | `templates/status-update.md` | Proposed |
| R14 | **Report assembly starts at the midpoint** (halfway through the event, about 5pm): the report writer copies `templates/report.md` to `~/cptc-work/report.md` and start pulling findings in. | The final hours are where CPTC10 reports degraded | `README.md` → Workflow; `checklists/00-kickoff.md` | Proposed |
| R15 | **QA before every submission,** run by someone who didn't write the section. | Placeholders, broken TOCs and count mismatches were common judge complaints | `checklists/50-report-qa.md` | Proposed (Phil ✓ on separate file) |
| R16 | **Credentials stay in the environment.** Report them redacted to the first and last characters. | Public repo; professionalism | `checklists/40-evidence-and-logging.md`; `templates/tracker/README.md` | Proposed |
| R17 | **Tracker:** each person edits only their own rows; the findings index has one owner (owner TBD; see "Who owns which team jobs?" in `OPEN-ITEMS.md`). Sharing method TBD (blocked by the shared-storage question; see `OPEN-ITEMS.md`). | Avoids overwrites | `templates/tracker/README.md` | Proposed |
| R18 | **Everyone edits only their own files; the report writer edits only `report.md`.** Changes to a finding go back to its author until the finding is pasted into `report.md`; after that, changes are made in `report.md`. Paste each finding once, when `compile.py` shows it READY (re-pasting would overwrite edits made in `report.md`). `incoming/` is a read-only mirror. | No two people ever edit copies of the same finding; no file moves or tool special cases | `README.md` → Working copy; `WORKFLOWS.md` | Proposed (tentative) |

## 3. Naming and format conventions

| Convention | Format | Documented in |
|---|---|---|
| Placeholder markers | `[[FIELD]]`, `[[CHOOSE: a / b]]`, `[[NOTE: …]]`, `[[TODO: …]]`. UPPER_SNAKE_CASE names, `/` between options. (Phil ✓) | `templates/README.md` |
| Checklist command arguments | `<range>`, `<host>`, `$DC`: typed at the terminal, never markers (one exception: the `PREP_` markers in `checklists/40`, filled before Oct 30) | `templates/README.md` |
| Finding IDs and files | `F-001`, … (allocation TBD, R6); `findings/F-001-short-name.md` | `templates/README.md` |
| Incident report IDs | `IR-001`, …; files `IR-001-short-name.md` | `templates/README.md` |
| Other event files (type prefix) | `NOTE-short-name.md`, `SU-short-name.md` (status update), `INJ-short-name.md` (inject response). The prefix says what the file is; it's never a `[[ ]]` tag, which QA would flag. `notebook.py` builds these names from a title and a type dropdown. | `tools/BUILD-SPEC.md` |
| Evidence files | `evidence/F-001-01.png`; Burp items `evidence/F-001-01-request.txt` | `checklists/40-evidence-and-logging.md` |
| Terminal logs | `~/cptc-logs/<name>_<UTC time>.log` and `.cmds.log` | `scripts/logged-shell.md` |
| Dates and times | `YYYY-MM-DD`, `HH:MM` (24-hour, local) | `templates/README.md` |
| Severity | Always written as a word (Critical / High / Medium / Low / Informational), never shown by color alone | `templates/severity-guide.md` |
| CVSS | `CVSS:3.1/AV:…` vector plus score | `templates/severity-guide.md` |
| Event folders | `~/cptc-work/` working copy (the report is `~/cptc-work/report.md`); `field-notes/<name>/` for notes; `incoming/<name>/` for teammates' files | `README.md` → Working copy; `tools/BUILD-SPEC.md` |
| Checklist numbering | `00` kickoff, `10` AD, `20` web, `30` OT, `40` evidence, `50` report QA, `60` AI/LLM | `README.md` → Layout |
| Findings library status | ☐ not written, ◐ drafted, ☑ reviewed against a winning report | `findings-library/README.md` |
| Unconfirmed items | Anything we assumed but couldn't confirm is tagged "Unconfirmed" (or "TBD") **and names the open question that blocks it**. The full list is in `OPEN-ITEMS.md`. Search the repo for `Unconfirmed` and `TBD` to find them; each must appear in that list | `OPEN-ITEMS.md` |
| Text format | Markdown, which in practice means plain text. Structure comes from the templates: headings and labelled list lines (`- **Severity:** …`). Tables only in `report.md` and in `compile.py` output | `templates/README.md`; `tools/BUILD-SPEC.md` |
