"""Intentional violation fixtures for the no-mocks AST hook tests.

Files in this directory are excluded from
:func:`scripts.check_no_mocks._iter_targets`'s default sweep so that
the directory walker does not flag fixtures it is being asked to test.
Tests load the fixtures by explicit path.
"""
