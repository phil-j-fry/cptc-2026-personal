# OT / ICS (Rides) Safe-Testing Sheet

> Treat ride control as **safety-critical**. In real OT work, the deliverable is mostly **finding and reporting exposure**, not exploitation. Breaking a ride is the fastest way to lose points and to need an incident report.

## Before touching anything
> **Unconfirmed:** the "no writes" limits on this sheet are our own safety policy, not a known rulebook rule. Blocked by the open question "What are the rules for OT / ride systems?"

- [ ] Re-read the ROE for OT. Is active testing allowed at all? Which hosts?
- [ ] Tell the team before any traffic to suspected OT ranges
- [ ] If anything is unclear, **ask Operations first**

## Identify (low impact)
- [ ] Find OT from the IT side first: hostnames, DNS, AD objects, shares (HMI project files, ladder logic backups, vendor docs)
- [ ] Common ports to recognize: 502 (Modbus/TCP), 102 (S7comm), 44818 / UDP 2222 (EtherNet/IP), 20000 (DNP3), 47808/UDP (BACnet), plus VNC and web UIs on HMIs
- [ ] If scanning is allowed: **TCP connect, specific ports, slow**, e.g. `nmap -sT -Pn -p 502,102,44818 --max-rate 10 <host>`. No `-A`, no version-intensity sweeps, no UDP floods.
- [ ] Read-only identification only if allowed, e.g. `nmap -sT -p 502 --script modbus-discover <host>` (one host at a time)

## Brittle ports: exclude from every broad or aggressive scan
Many controllers crash or misbehave when version detection or scripts hit their industrial service. Add this exclusion to **every** broad `nmap` scan on any range that might hold OT:

```
--exclude-ports T:102,502,789,1089-1091,1883,1911,1962,2404,2455,4000,4840,4911,5006-5007,5094,8883,9600,18245-18246,20000,34962-34964,44818,48898,U:1089-1091,2222,4000,9600,20000,34962-34964,34980,44818,47808,48899
```

| Port(s) | Protocol |
|---|---|
| TCP 102 | Siemens S7comm (ISO-TSAP) |
| TCP 502 | Modbus/TCP |
| TCP 789 | Red Lion Crimson |
| TCP/UDP 1089–1091 | Foundation Fieldbus HSE |
| TCP 1883, 8883 | MQTT (plain / TLS) |
| TCP 1911, 4911 | Niagara Fox (building automation) |
| TCP 1962 | PCWorx (Phoenix Contact) |
| TCP 2404 | IEC 60870-5-104 |
| TCP 2455 | CODESYS |
| TCP/UDP 4000 | Emerson ROC Plus |
| TCP 4840 | OPC UA |
| TCP 5006–5007 | Mitsubishi MELSEC |
| TCP 5094 | HART-IP |
| TCP/UDP 9600 | Omron FINS |
| TCP 18245–18246 | GE SRTP |
| TCP/UDP 20000 | DNP3 |
| TCP/UDP 34962–34964 | PROFINET |
| UDP 34980 | EtherCAT |
| TCP/UDP 44818, UDP 2222 | EtherNet/IP (Rockwell / Allen-Bradley) |
| TCP 48898, UDP 48899 | Beckhoff ADS/AMS |
| UDP 47808 | BACnet/IP |

- **The port list is a safety net, not a guarantee.** Some devices fall over from plain host discovery. As soon as you identify an OT host, tell the team aloud, write it on the whiteboard, and add it to `~/cptc-work/ot-hosts.txt` (everyone appends it to their own copy; no tool shares the file. **TBD:** blocked by the open question "Is shared storage or a shared document provided?"). Use `--excludefile ~/cptc-work/ot-hosts.txt` on all broad scans. From then on, touch it only with the low-rate checks above.
- The list was built from Stanford's public CPTC scan harness (`blitzHarness/nmap/excluded_ports_services.txt`) plus other common ICS ports. Add anything the scope document names.

## Never (unless the ROE explicitly says otherwise, in writing)
- Write coils or registers, change setpoints, upload or download PLC programs, or put a PLC in stop or program mode
- Run vulnerability scanners or fuzzers against controllers
- Brute force HMI logins

## What makes a strong OT finding
- **Reachability:** "From the guest Wi-Fi / corporate LAN, an attacker can reach the ride control network" (segmentation failure)
- Default or shared credentials on HMIs and engineering workstations
- Unauthenticated industrial protocols exposed beyond the control network
- Engineering workstations joined to the corporate domain with paths from compromised users
- Impact written in **safety and operational** terms, with remediation following IEC 62443 zones and conduits
