# Templates: Usage Key

Every template in this repo uses the same placeholder markers. That way one search before submission finds everything that still needs filling in or deleting.

## Placeholder markers

| Marker | Meaning | Example | What to do with it |
|---|---|---|---|
| `[[FIELD_NAME]]` | A value to fill in | `[[CLIENT_NAME]]`, `[[HOST_IP]]` | Replace the whole marker, brackets included, with the real value |
| `[[CHOOSE: A / B / C]]` | Pick one option | `[[CHOOSE: Critical / High / Medium / Low / Informational]]` | Keep only the option you chose |
| `[[NOTE: ...]]` | Guidance for the writer | `[[NOTE: One page, written last.]]` | Read it, follow it, then delete the whole marker |
| `[[TODO: ...]]` | Study-day work in `findings-library/` | `[[TODO: root cause in your own words]]` | Write it during study. None may remain on competition day |

Rules:

- **Why `[[ ]]`:** it doesn't collide with things that legitimately appear in pentest evidence. `{{ }}` would collide with template-injection payloads (`{{7*7}}`) and Jinja-based report tools, and `<< >>` with shell heredocs (`<<EOF`). Bash tests do use `[[`, but always with a space after (`[[ -f x ]]`), so the QA search skips them.
- **Names are UPPER_SNAKE_CASE: capital letters and underscores only, no spaces and no digits** (write `[[SECOND_HOST]]`, not `[[HOST2]]`). That's what keeps the QA search exact: it matches `[[` followed immediately by uppercase letters.
- **If you write in Obsidian,** it will show `[[...]]` as links. That's harmless; the text stays visible.
- **Options are separated with `/`, not `|`.** A `|` inside a Markdown table cell would split the column.
- **One item's details are labelled list lines, not a table:** `- **Severity:** High`. Tables appear only in `report.md` and in what `compile.py` generates, because a `|` or a line break typed into a value breaks a table. Keep the leading `- `: without it, Markdown joins consecutive lines into one paragraph when rendered.
- **The same name always means the same value.** `[[CLIENT_NAME]]` is the client's name everywhere it appears, so you can find-and-replace it in one go. If a template needs two different values of the same kind, give each its own name: `[[TIME_DETECTED]]`, `[[TIME_REPORTED]]`. A section that holds a variable number of items, such as reproduction steps, gets one marker for the whole section (`[[REPRODUCTION_STEPS]]`) rather than one per item. The one exception is the repeating rows and list items in `report.md` (one per finding, per roadmap action, per top risk). Those are patterns you copy once per item, so their markers repeat on purpose.
- **One exception to the checklist rule below:** `checklists/40-evidence-and-logging.md` has a few `PREP_` markers for decisions the team fills in before the event (theme, font). They are meant to be found and filled by Oct 30.
- **Checklists use a different style on purpose.** Command arguments in `checklists/` are written `<range>`, `<host>`, `$DC` and so on. Those get typed at the terminal and never reach the report, so they're not markers.
- **A finished deliverable contains zero markers.** `checklists/50-report-qa.md` has the search command.

### Standard field names

Use these names rather than inventing new ones for the same thing.

| Name | Format |
|---|---|
| `[[CLIENT_NAME]]`, `[[CLIENT_CONTACT]]` | As written in the scope document |
| `[[FIRM_NAME]]`, `[[SENDER_NAME]]`, `[[TESTER]]` | Our in-character firm name and people. No school identifiers |
| `[[FINDING_ID]]`, `[[FINDING_TITLE]]` | `F-001`, `F-002`, … (allocation TBD, R6) |
| `[[IR_ID]]`, `[[REFERENCE]]` | `IR-001`, `IR-002`, … (`[[REFERENCE]]` is the IR or inject a `report.md` timeline row points to) |
| `[[DATE]]`, `[[TIME]]`, and suffixed forms like `[[TIME_DETECTED]]` | `YYYY-MM-DD`, `HH:MM` (24-hour, local) |
| `[[ENGAGEMENT_START]]`, `[[ENGAGEMENT_END]]`, `[[REPORT_DATE]]` | `YYYY-MM-DD` |
| `[[HOST]]`, `[[HOST_IP]]`, `[[URL]]`, `[[ACCOUNT]]` | As observed |
| `[[CVSS_VECTOR]]`, `[[CVSS_SCORE]]` | `CVSS:3.1/AV:N/AC:L/...` and `9.8` |

## Which template, when

| Template | Use it for | Who fills it | When |
|---|---|---|---|
| `finding.md` | One file per finding, copied to `findings/F-XXX-short-name.md` | The finder (R18) | The moment a finding is confirmed |
| `severity-guide.md` | Reference, not a deliverable | Whoever makes severity calls (owner TBD; see "Who owns which team jobs?" in `OPEN-ITEMS.md`) | When assigning or reviewing severity |
| `report.md` | The final report. Copied once to `~/cptc-work/report.md` (not into `findings/`) | The report writer | Copied at the midpoint, about 5pm; see `WORKFLOWS.md` |
| `incident-report.md` | Anything we caused or might have caused | owner TBD; see "Who owns which team jobs?" in `OPEN-ITEMS.md` | Timing TBD (see the incident-report question) |
| `status-update.md` | Scheduled or ad-hoc progress messages to the client | owner TBD; see "Who owns which team jobs?" in `OPEN-ITEMS.md` | Midpoint, and whenever a critical is found |
| `inject-response.md` | A client request during the event | owner TBD; see "Who owns which team jobs?" in `OPEN-ITEMS.md` | Before the inject's due time |
| `presentation-outline.md` | Planning the debrief slides | Whole team | After the report is submitted |
| `tracker/` | Hosts, credentials, created accounts and artifacts, attack path, and findings index (CSV) | Everyone (own rows); findings index owner TBD; see "Who owns which team jobs?" in `OPEN-ITEMS.md` | Copied to `~/cptc-work/tracker/` at kickoff. Sharing method TBD (blocked by the shared-storage question in `OPEN-ITEMS.md`); see `tracker/README.md` |

## The workflow from finding to report

1. Confirm the finding and take an ID straight away (how IDs are allocated is **TBD**, R6; blocked by the open question "Is shared storage or a shared document provided?" in `OPEN-ITEMS.md`).
2. Copy `templates/finding.md` (or a matching `findings-library/` entry) to `findings/F-XXX-short-name.md`.
3. Fill every `[[FIELD]]`, resolve every `[[CHOOSE]]`, and delete every `[[NOTE]]` as you go.
4. Hand it to the report writer. You keep editing your own file until it's pasted into `report.md`; after that, changes are made in `report.md` (R18). A finding without complete reproduction steps is sent back (R7); who makes the final severity call is TBD (R8).
5. At the midpoint the report writer copies `templates/report.md` to `~/cptc-work/report.md` and pastes the finished findings into it, ordered by severity (`WORKFLOWS.md`).
6. Before every submission, run `checklists/50-report-qa.md`.
