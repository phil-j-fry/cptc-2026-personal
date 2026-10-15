# OT / ICS (Rides) Safe-Testing Sheet

> Treat ride control as **safety-critical**. In real OT work, the deliverable is mostly **finding and reporting exposure**, not exploitation. Breaking a ride is the fastest way to lose points and to need an incident report.

## Before touching anything
- [ ] Re-read the ROE for OT. Is active testing allowed at all? Which hosts?
- [ ] Tell the lead before any traffic to suspected OT ranges
- [ ] If anything is unclear, **ask Operations first**

## Identify (low impact)
- [ ] Find OT from the IT side first: hostnames, DNS, AD objects, shares (HMI project files, ladder logic backups, vendor docs)
- [ ] Common ports to recognize: 502 (Modbus/TCP), 102 (S7comm), 44818 / UDP 2222 (EtherNet/IP), 20000 (DNP3), 47808/UDP (BACnet), plus VNC and web UIs on HMIs
- [ ] If scanning is allowed: **TCP connect, specific ports, slow**, e.g. `nmap -sT -Pn -p 502,102,44818 --max-rate 10 <host>`. No `-A`, no version-intensity sweeps, no UDP floods.
- [ ] Read-only identification only if allowed, e.g. `nmap -sT -p 502 --script modbus-discover <host>` (one host at a time)

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
