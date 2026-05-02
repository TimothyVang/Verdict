# demo-assets/

Demo recording assets for the SANS FIND EVIL! 2026 submission.

Files expected here (produced during W5/W6):

| File | Phase | Description |
|------|-------|-------------|
| `rough-cut.mp4` | W5.E | Rough 5-min cut for internal review |
| `final-cut.mp4` | W6.B | Final 5-min submission cut |
| `tsi-host-egress.pcap` | W3.B.2 | tcpdump host-egress capture proving TSI injects bearer |
| `tsi-vm-internal.pcap` | W3.B.2 | tcpdump VM-internal capture proving bearer absent in VM |
| `langfuse-dashboard.json` | W5.E.3 | Langfuse dashboard export |
| `case_001.md` | W4.A | Case 001 manual verification notes |

The `*.pcap` files are gitignored (large binary, not needed in source repo).
The `*.mp4` files are gitignored and hosted externally (Devpost video link).

See `docs/DEMO_SEQUENCE.md` for the recording script and tcpdump filters.
