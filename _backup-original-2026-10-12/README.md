# CCSF CPTC Team Repo

Pre-staged templates, checklists, and scripts for the Collegiate Penetration Testing Competition (CPTC12, Regionals).

## Rules that govern this repo (from the official rulebook, Oct 2025 revision)

- **This repo is public.** Other teams and the internet can read it. Never put credentials, client data, or anything from the competition environment in here before the event ends.
- **Request deadline:** the repo must be requested at least **14 days before** the event. The request comes from a school email and includes the school name and every member's account name.
- **Freeze:** no commits during the **7 days before** the event. During competition hours, changes may be made only from inside the competition environment.
- **Be ready to explain anything in `scripts/`.** Operations may ask you to demonstrate it.
- **No coach commits.**
- **No outside collaboration tools** (Google Docs, M365, Dropbox) unless officials provide them. The templates here are Markdown so they work in whatever environment we're given.
- **Printed checklists are allowed.** Print everything in `checklists/` before the event.

Re-check the current rulebook (https://cp.tc/docs/cptc-rules.pdf) before the event in case these rules change.

## Layout

| Path | What it is |
|---|---|
| `templates/` | Report, finding, incident-report, status-update, inject-response, and presentation templates |
| `findings-library/` | 22 pre-written findings, one written per study day. Copy one into `findings/` on the day |
| `checklists/` | Printable run sheets: kickoff, AD, web, OT-safe, evidence |
| `notes/` | Study notes plus `technique-map.md` (what to study, by week, with sources). Anything useful becomes a checklist line before the freeze |
| `scripts/` | Small helpers we can explain line by line |
| `findings/` | One file per finding during the event (`F-001-short-name.md`) |
| `evidence/` | Screenshots and logs, named to match the finding ID |

## Roles (fill in)

| Role | Person | Owns |
|---|---|---|
| Lead / report editor | | Scope, client contact, severity, final report, incident reports |
| AD / internal | | Domain attack paths |
| Web / patron systems | | Ticketing, POS, web apps |
| Enumeration + evidence | | Checklists, command logs, screenshots, first-draft findings |

## The workflow on the day

1. Kickoff checklist: read the scope and ROE aloud, then write the out-of-scope list on the whiteboard.
2. Everyone starts a logged shell (`scripts/logged-shell.sh`).
3. Every finding gets an ID the moment it's found, before it gets exploited further.
4. The drafter fills in `templates/finding.md`. The lead edits it and assigns severity.
5. If something breaks, stop, tell the lead, and file `templates/incident-report.md` within the hour.
6. Report assembly starts at the halfway point, not at the end.
