# Examiner Caveats - Tier-1 (always loaded)

## AMCACHE_LASTMODIFIED_NOT_EXEC
Amcache `LastModified` reflects catalog registration time, not execution time. Execution claims based on Amcache alone are unsafe; require corroboration from Prefetch, EVTX 4688, or Sysmon EID 1.

## SHIMCACHE_ORDER_CHANGED_WIN81
ShimCache ordering is LRU on Windows 8 and earlier, and insertion-order on Windows 8.1 and later. Do not assume chronological order on modern Windows.

## PREFETCH_SSD_DISABLED
Prefetch may be disabled on SSDs by GPO or driver default. Absence of a Prefetch entry is not evidence of non-execution.

## MFT_SI_STOMPABLE
`$STANDARD_INFORMATION` timestamps are stompable by user-mode malware. Prefer `$FILE_NAME` timestamps for evidentiary claims.

## USNJRNL_WRAPS
The USN Journal is a circular buffer; gaps may reflect wrapping rather than tampering. Treat absence carefully.

## LOGON_TYPE_3_VS_10
EVTX 4624 Logon Type 3 is network logon. Type 10 is RemoteInteractive/RDP. Conflating them mis-attributes intrusion vectors.

## SYSMON_PROCESSGUID_OVER_PID
Sysmon EID 1 `ProcessGuid` is the correlation key. PID is reused; never use PID alone across time windows.
