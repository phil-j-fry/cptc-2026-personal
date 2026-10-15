# F-XXX: <Short, specific title: what is wrong and where>

| Field | Value |
|---|---|
| Severity | Critical / High / Medium / Low / Informational (see `templates/severity-guide.md`) |
| CVSS 3.1 | `CVSS:3.1/AV:_/AC:_/PR:_/UI:_/S:_/C:_/I:_/A:_` (score) |
| Affected assets | hostname (IP), URL, account |
| Discovered by / when | name, `YYYY-MM-DD HH:MM` (local) |
| Status | Confirmed / Exploited / Suspected |
| References | CWE-___, ATT&CK T____, vendor advisory |

## Summary
Two or three sentences a non-technical manager can follow: what is wrong, what an attacker could do with it, and why the business should care. Use the client's terms (rides, ticketing, guest data), not tool names.

## Business impact
What this means for the client specifically: guest safety, payment data, park operations, reputation, compliance (e.g., PCI DSS for card data). Be concrete and don't inflate it.

## Technical detail
How the vulnerability works and the root cause, not just the symptom.

## Reproduction steps
Numbered, copy-pasteable, from the tester's starting position. State any prerequisites, such as needing domain-user credentials.

1. `command`
2. `command`

## Evidence
- `evidence/F-XXX-01.png`: what it shows
- Log excerpt (timestamps included):

```
[YYYY-MM-DD HH:MM:SS] ...
```

## Remediation
- **Immediate:** the specific fix (setting, patch version, config line).
- **Longer term:** the control that stops this class of issue.
- **How to verify the fix:** a command or check the client can run.

## Attack chain
Was this a step in a larger path? Link to the related findings: F-___ → this → F-___.
