# downloads/

Place for **large binary artifacts** that are not tracked in git. Both subdirectories are gitignored placeholders today — populate them manually before running cases or evals.

## Layout

```
downloads/
├── README.md             ← this file
├── sift-workstation/     ← SANS SIFT Workstation OVA (8.81 GB)
└── evidence-samples/     ← case evidence (disk images, memory captures, pcaps)
```

## sift-workstation/

The SIFT VM appliance. Required to run VERDICT against real evidence.

- **Source:** https://www.sans.org/tools/sift-workstation
- **Format:** OVA (8.81 GB, last updated April 24 2026)
- **Auth:** SANS Portal login required
- **Default credentials:** `sansforensics` / `forensics`; `sudo su -` to elevate
- **Hash verify:** MD5 / SHA1 / SHA256 published on the SANS download page

Alternative install paths (no OVA download):
```bash
# Native Ubuntu 22.04
sudo cast install teamdfir/sift

# WSL
sudo cast install --mode=server teamdfir/sift-saltstack
```

## evidence-samples/

Ground-truth case data referenced by the VERDICT eval harness. Three engineered cases per `../docs/spec/VERDICT_MASTER_BUILD_PLAN.md`:

- `case_001_lolbins/` — 17 indicators (LOLBins compromise)
- `case_002_credtheft/` — 17 indicators (credential theft)
- `case_003_ransomware/` — 16 indicators (Honeynet-derivative ransomware)

**Distribution:** evidence files are shared via the hackathon Slack channel, not via a public URL.

- **Slack invite:** https://join.slack.com/t/sansaihackathon/shared_invite/zt-3srjz86zo-bwHi_v1aKTg2IJAU4_4OwA
- **Contact:** aihackathon@sans.org

Once downloaded, populate as:
```
downloads/evidence-samples/
├── case_001_lolbins/
│   ├── memory.mem
│   ├── disk.E01
│   └── manifest.json
├── case_002_credtheft/
└── case_003_ransomware/
```

## Reminder — no mocks (CLAUDE.md §3.10)

These are **real evidence files**, used by the dev loop, eval loop, and demo loop alike. Do not fabricate synthetic substitutes. If files aren't available, tests should fail loudly via `verdict doctor`, not paper over the gap with a mock.
