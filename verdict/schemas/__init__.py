"""Pydantic v2 schemas (W1.B, W1.C.3, W1.F).

Schema modules live here; they are leaf-level (do not import from
`verdict.runtime`, `verdict.graph`, `verdict.tools`). The runtime
imports schemas, not the other way around.

`VerdictStatus` is the canonical 6-state enum from CLAUDE.md §3.6.
W1.B.13 may extend the schema-layer enum with extra metadata
(value strings, ordering); the *member set* is frozen by §3.6.
"""
