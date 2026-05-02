"""verdict/schemas/version.py — centralised schema version constant.

All top-level schemas import SCHEMA_VERSION from this module and assign it as
the default for their `schema_version: int` field.  Bumping from v1 to v2 is a
coordinated change: update this constant, update the field default on every
top-level model, write a migration in verdict/schemas/migration.py, and bump
the version pin in the BUILD_PLAN gate.

Current version: 1
"""

SCHEMA_VERSION: int = 1
