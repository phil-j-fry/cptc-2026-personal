# Severity Guide

Rate with **CVSS 3.1 for the technical score**, then adjust the reported severity for **business context**, and write down why. Judges reward consistent, justified ratings more than high ones.

| Severity | CVSS | Typical examples |
|---|---|---|
| Critical | 9.0–10.0 | Domain Admin compromise; unauthenticated RCE on an internet-facing host; ability to change ride or PLC state; bulk cardholder data exposure |
| High | 7.0–8.9 | Authenticated RCE; crackable Kerberoastable service account with admin rights; ESC1-vulnerable certificate template; SQLi exposing guest PII |
| Medium | 4.0–6.9 | SMB signing not required (relay possible); IDOR exposing other guests' tickets; weak password policy |
| Low | 0.1–3.9 | Verbose errors; missing security headers with no demonstrated impact |
| Informational | — | Hardening advice, positive observations |

## Context adjustments (state them in the finding)
- **Raise** for: guest physical safety (rides), payment data (PCI DSS), being a step in a demonstrated chain to full compromise.
- **Lower** for: requires unlikely preconditions, or compensating controls were observed.

## Consistency rule
The lead assigns the final severity for every finding, so the report reads as one voice.
