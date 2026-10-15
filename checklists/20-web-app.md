# Web / Patron Systems Run Sheet (ticketing, POS, guest apps)

## Map it
- [ ] List every web service from the nmap output (80, 443, 8080, 8443, and anything else that speaks HTTP)
- [ ] Proxy everything through Burp. Browse every feature as a normal user first.
- [ ] Content discovery at a polite rate: `ffuf -u https://<host>/FUZZ -w <wordlist> -rate 20`
- [ ] Fingerprint the stack and versions → check known CVEs for those exact versions
- [ ] Look for `robots.txt`, `.git/`, backup files, API docs (`/swagger`, `/api/docs`), and default admin panels

## Authentication and sessions
- [ ] Default and weak credentials on admin panels (check the ROE on brute force)
- [ ] Username enumeration via login, reset, or registration messages
- [ ] Password reset flow: token predictability, reuse, host header injection
- [ ] Session cookie flags, logout invalidation, fixation

## Access control (the highest-yield area for patron systems)
- [ ] IDOR: change IDs in tickets, orders, profiles, and receipts (`/ticket/1001` → `1002`)
- [ ] Horizontal: can guest A see guest B's data?
- [ ] Vertical: can a guest reach staff or admin functions directly?
- [ ] API endpoints the UI doesn't show

## Injection
- [ ] SQLi in search, filters, and IDs (manual first; `sqlmap` only with a low `--risk`/`--level` and never against write endpoints without thinking)
- [ ] XSS in anything reflected or stored (reviews, names, notes)
- [ ] Command injection or SSRF in any "fetch URL", import, or export feature
- [ ] File upload: type checks, where files land, and whether they execute

## Business logic (theme park specific)
- [ ] Ticket price or quantity tampering, negative quantities, coupon reuse
- [ ] Skipping payment steps in a multi-step checkout
- [ ] Fast-pass, queue, or loyalty-point manipulation

## Data sensitivity
- [ ] Card data visible anywhere → PCI DSS context, rate severity accordingly
- [ ] Guest PII exposure (names, emails, birthdays, photos) → privacy impact
