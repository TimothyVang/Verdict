# Examiner Caveats — Tier-1 (always loaded)

These seven caveats are mandatory for every executor invocation. When a Finding
cites an artifact class that triggers a caveat, the `CaveatID` MUST appear in
`Finding.caveats_acknowledged`. Omission causes schema validation failure.

---

## AMCACHE_LASTMODIFIED_NOT_EXEC

**Trigger:** Any citation of Amcache (ArtifactClass.AMCACHE).

**Caveat:** Amcache `LastModified` reflects the time the entry was written to
the hive — typically when the executable was first catalogued by the Application
Compatibility subsystem. It is **NOT** the execution time. A file may be
catalogued during installation, browsing, or background indexing without ever
being executed by the user. Execution claims based on Amcache alone are
forensically unsafe; require corroboration from at least one of: Prefetch
(last-run timestamp, run count), EVTX Event ID 4688 (Process Creation), or
Sysmon EID 1 (Process Created with `CommandLine`).

**Acknowledgment required:** `CaveatID.AMCACHE_LASTMODIFIED_NOT_EXEC`

---

## SHIMCACHE_ORDER_CHANGED_WIN81

**Trigger:** Any citation of ShimCache (AppCompatCache).

**Caveat:** On Windows ≤ 8 (including Vista and 7), ShimCache entries are
ordered from most-recently-used (LRU) to least-recently-used, so entry order
reflects rough temporal execution sequence. On Windows ≥ 8.1 (including all
modern Windows 10/11 builds), the ordering changed to **insertion-order** as
entries are added; this means the order no longer reliably reflects execution
recency. Do **not** assume chronological ordering on modern Windows systems
without corroboration from another execution artifact.

**Acknowledgment required:** `CaveatID.SHIMCACHE_ORDER_CHANGED_WIN81`

---

## PREFETCH_SSD_DISABLED

**Trigger:** Any citation of Prefetch (ArtifactClass.PREFETCH).

**Caveat:** Windows Prefetch may be disabled on SSD-only hosts. The
`PrefetchParameters` registry key (`HKLM\SYSTEM\CurrentControlSet\Control\Session
Manager\Memory Management\PrefetchParameters`) controls this; value `EnablePrefetcher`
set to 0 or 1 disables or limits Prefetch. Group Policy can also disable it.
On NVMe and SATA SSDs, Windows 8+ may set `EnablePrefetcher=0` automatically.
**Absence of a Prefetch entry is not evidence of non-execution** — it may simply
mean Prefetch is disabled. Corroborate with Amcache, EVTX 4688, or Sysmon EID 1.

**Acknowledgment required:** `CaveatID.PREFETCH_SSD_DISABLED`

---

## MFT_SI_STOMPABLE

**Trigger:** Any use of `$STANDARD_INFORMATION` ($SI) timestamps for evidentiary
claims (ArtifactClass.MFT with $SI timestamps).

**Caveat:** `$STANDARD_INFORMATION` timestamps (Created, Modified, MFT Modified,
Accessed) are modifiable by **user-mode malware** using the `NtSetInformationFile`
API (timestomping) or `SetFileTime` Win32 call. An adversary can retroactively
alter these timestamps to blend into the filesystem noise without kernel-level
privileges. Prefer `$FILE_NAME` ($FN) timestamps, which are updated by the NTFS
kernel driver and require significantly higher privilege to forge. When only $SI
timestamps are available, note this limitation explicitly and mark findings as
lower-confidence. MFTECmd output distinguishes $SI vs $FN — use `$FN` columns
for evidentiary claims.

**Acknowledgment required:** `CaveatID.MFT_SI_STOMPABLE`

---

## USNJRNL_WRAPS

**Trigger:** Any citation of USN Journal entries (ArtifactClass.MFT or explicit
USN Journal references).

**Caveat:** The USN Journal (`$UsnJrnl:$J`) is a **circular buffer** of fixed
maximum size (typically 32 MB by default, configurable via `fsutil usn
queryjournal`). When the buffer fills, the oldest entries are overwritten.
On active systems, the journal may wrap multiple times per day. **Gaps in the
USN Journal timeline should not be interpreted as tampering** — they may simply
reflect normal circular-buffer wrapping. When citing USN entries older than the
estimated wrap window, acknowledge that earlier activity may be unrecorded.
Compare the `FirstUsn` vs `NextUsn` values from `fsutil usn queryjournal` to
estimate the journal's age range before drawing conclusions about coverage.

**Acknowledgment required:** `CaveatID.USNJRNL_WRAPS`

---

## LOGON_TYPE_3_VS_10

**Trigger:** EVTX Event ID 4624 (ArtifactClass.EVTX_4624) where `LogonType`
equals 3 or 10.

**Caveat:** Windows Security Event 4624 (Logon Success) uses `LogonType` to
distinguish the authentication mechanism:
- **Type 3 = Network logon** — authentication over the network (SMB file share
  access, API call, WMI, etc.). The credentials were passed over the network
  but no interactive session was created on the target. Common for lateral
  movement via SMB/PsExec-style techniques.
- **Type 10 = RemoteInteractive** — RDP session (Terminal Services). An
  interactive desktop session was created on the target machine.

**Do not conflate these.** Calling Type 3 "RDP" misattributes the intrusion
vector and can send the investigation in the wrong direction. When reporting
lateral movement via Event 4624, always state the exact LogonType and what it
implies about the access mechanism.

**Acknowledgment required:** `CaveatID.LOGON_TYPE_3_VS_10`

---

## SYSMON_PROCESSGUID_OVER_PID

**Trigger:** Any Sysmon-based process correlation (ArtifactClass.SYSMON_1 or
other Sysmon event classes).

**Caveat:** Windows Process IDs (PIDs) are **reused** by the kernel after a
process exits. On a busy system a PID can be recycled within seconds. When
correlating Sysmon events across time windows (e.g., linking a Sysmon EID 1
Process Creation to a subsequent Sysmon EID 3 Network Connection or EID 11
FileCreate), you **must** use the `ProcessGuid` field, not PID. `ProcessGuid`
is a GUID assigned by Sysmon at process creation time and is unique across the
lifetime of a case. Using PID alone for cross-event correlation risks linking
unrelated processes that happen to share a recycled PID, producing false-positive
findings. Always cite `ProcessGuid` in rationale when correlating Sysmon events.

**Acknowledgment required:** `CaveatID.SYSMON_PROCESSGUID_OVER_PID`
