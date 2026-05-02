# VERDICT Schema Migration Policy (v1)

**Document type:** Schema versioning and migration strategy for VERDICT.
**Authority:** Per BUILD_PLAN.md Phase W1.G.4.
**Scope:** Policy for evolving Pydantic schemas while maintaining backward compatibility.

---

## Executive summary

VERDICT uses Pydantic v2 schemas for all top-level domain objects: Finding, Hypothesis, InvestigationPlan, ToolOutput, LedgerEntry, VerificationResult. Each schema includes a schema_version: int field (default: 1) to track the data format version.

Breaking schema changes are NOT applied in-place to existing cases. Instead:
1. The new schema gets a new version number (e.g., v2).
2. A migration script (migrations/v1_to_v2.py) is authored and tested.
3. Old cases remain immutable in v1 format in the ledger.
4. The verdict reverify command re-runs verification under the new schema version (if needed).

This ensures chain-of-custody integrity: ledger entries are never mutated, only migrated for re-processing.

## Versioning convention

### Schema version field

All top-level schemas include:

    class Finding(BaseModel):
        schema_version: int = 1  # Current version
        finding_id: str
        # ... other fields ...

### Version numbering

- Version starts at 1.
- Increments by 1 for each breaking change.
- Non-breaking additions (new optional fields with defaults) do NOT require a version bump.

### Examples of breaking changes

- Renaming a required field.
- Removing a field entirely.
- Changing the type of a field.
- Changing a field from optional to required (unless a default is added).
- Changing enum values.

### Examples of non-breaking changes

- Adding a new optional field with a default value.
- Adding a new optional field with nullable=True.
- Widening a field type with backward-compatible parsing.
- Refactoring internal validation logic (if external schema unchanged).

---

## Migration script structure

Each breaking change ships a migration script in verdict/migrations/:

**File:** verdict/migrations/v1_to_v2.py

Example structure:

    def migrate_finding_v1_to_v2(finding_dict):
        from verdict.schemas.finding import Finding as FindingV1
        from verdict.schemas.finding_v2 import Finding as FindingV2
        
        # Validate input is v1
        finding_v1 = FindingV1(**finding_dict)
        
        # Transform fields
        v2_dict = {
            'schema_version': 2,
            'finding_id': finding_v1.finding_id,
            'mitre_techniques': [finding_v1.mitre_technique],  # Scalar -> List
            'artifact_refs': [
                {'path': p, 'line_number': None}
                for p in finding_v1.artifact_paths
            ],
            'status': finding_v1.status,
            'rationale': finding_v1.rationale,
        }
        
        # Validate v2 output
        finding_v2 = FindingV2(**v2_dict)
        return finding_v2.model_dump()

### Migration script requirements

- File naming: migrations/v{N}_to_v{N+1}.py
- Function naming: migrate_<schema_name>_v{N}_to_v{N+1}(dict) -> dict
- Input validation: Parse input with old schema (v1)
- Output validation: Parse output with new schema (v2)
- Idempotence: Running twice on same object = same result
- Error handling: Raise ValueError with clear message if cannot migrate
- Docstring: Include breaking changes and manual intervention required

---

## Migration workflows

### Scenario 1: New finding during a case (automatic)

Case runs under schema v1. Planner emits Finding matching v2 schema.

What happens:
1. LedgerEmitter receives v2 Finding.
2. LedgerEntry.schema_version = 2.
3. Entry recorded in ledger with schema_version=2.
4. No migration needed; v2 data recorded natively.

### Scenario 2: Resuming a case with schema drift (migration on read)

Case initialized with v1, ran to completion. Code upgraded to v2. User calls verdict resume or verdict show.

What happens:
1. LedgerEntry read from JSONL.
2. schema_version field checked: it's 1.
3. Migration handler routes to migrate_finding_v1_to_v2().
4. Finding migrated in-memory, returned to caller.
5. Ledger itself NOT mutated (immutable-by-design).

### Scenario 3: Re-verification under new schema

Case has mixed v1 and v2 findings. User calls verdict reverify <case_id> --mode cloud.

What happens:
1. All findings read from ledger.
2. v1 findings migrated to v2 in-memory.
3. Verifier processes under v2 schema constraints.
4. New verification results written to new case (reverify-<case_id>-cloud).
5. Original case ledger never modified.

---

## Backward compatibility guarantees

### Rule 1: Immutable ledger

Ledger entries (LedgerEntry objects) in JSONL are NEVER mutated on disk. Migration happens only in-memory during read.

Why: Chain-of-custody. If a tool call from May 2 is modified in June, audit trail is broken.

### Rule 2: Default values on new optional fields

New optional fields must have a default value:

    class Finding(BaseModel):
        schema_version: int = 2
        # ...
        severity_score: Optional[float] = None
        reviewed_by: Optional[str] = None

This allows v1 findings (without these fields) to load without migration errors.

### Rule 3: Lenient validation on read

When loading a Finding from ledger, validator should NOT raise error for missing new optional fields:

    finding = Finding.model_validate(finding_dict_from_ledger)
    assert finding.severity_score is None  # Default to None

---

## Migration testing

### Test 1: Forward migration

Test v1 object migrates to v2 without data loss:

    def test_migrate_finding_v1_to_v2():
        finding_v1_dict = {
            'schema_version': 1,
            'finding_id': 'finding_001',
            'mitre_technique': 'T1005.004',
            'artifact_paths': ['/registry/hklm/...'],
        }
        finding_v2_dict = migrate_finding_v1_to_v2(finding_v1_dict)
        finding_v2 = FindingV2(**finding_v2_dict)
        assert finding_v2.schema_version == 2
        assert finding_v2.mitre_techniques == ['T1005.004']

### Test 2: Idempotence

Test that migrating twice = same result:

    def test_migration_idempotent():
        finding_v1_dict = {...}
        migrated_once = migrate_finding_v1_to_v2(finding_v1_dict)
        migrated_twice = migrate_finding_v1_to_v2(migrated_once)
        assert migrated_once == migrated_twice

### Test 3: Backward compatibility

Test v2 code reads v1 ledger entries:

    def test_load_v1_ledger_entry_in_v2_code():
        ledger_entry_v1 = {'event_type': 'finding', 'finding': {...}}
        ledger_entry = LedgerEntry.model_validate(ledger_entry_v1)
        assert ledger_entry.event_type == 'finding'

---

## Rollout procedure

When introducing a breaking schema change (e.g., v1 -> v2):

1. **Prepare migration script** (verdict/migrations/v1_to_v2.py).
   - Implement forward migration.

2. **Update schema** (verdict/schemas/finding.py).
   - Increment schema_version to 2.
   - Add new fields with sensible defaults.

3. **Add backward-compat read path** in LedgerEntry.model_validate().
   - Detect schema_version field.
   - Apply migration if version < current.

4. **Test extensively**.
   - Unit tests for each schema.
   - Integration: resume v1 case and run to completion.
   - Mixed schema versions test.

5. **Deploy** the new code.
   - Operator upgrades VERDICT binary.
   - Old cases (v1) continue to work via automatic migration on read.
   - New cases use v2 schema.

6. **Optional: rebase old cases to v2**.
   - Run verdict reverify <case_id> to generate v2 copy.
   - This is optional; cases can exist with mixed schema versions indefinitely.

---

## Document history

| Version | Date | Notes |
|---------|------|-------|
| 1.0 | 2026-05-02 | Initial schema migration policy per BUILD_PLAN.md W1.G.4. Immutable ledger, versioning, migration structure. |
