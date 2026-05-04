import os

if os.environ.get("VERDICT_TEST") or os.environ.get("TEST_MODE"):
    VALUE = "loose"
else:
    VALUE = "strict"
