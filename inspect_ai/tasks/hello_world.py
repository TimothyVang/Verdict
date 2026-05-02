"""Minimal Inspect AI hello-world task for W1.A.8."""

from inspect_ai import Task, task
from inspect_ai.dataset import Sample
from inspect_ai.scorer import exact
from inspect_ai.solver import generate


@task
def hello_world() -> Task:
    """Minimal hello-world task for Inspect AI evaluation.

    This task creates a single sample that tests if the LLM
    can produce the expected output "Hello World". It uses the
    built-in generate() solver and exact() scorer to verify
    the output matches the target.

    This is the W1.A.8 infrastructure scaffold task for Inspect AI.
    It requires a model to be specified via the model parameter,
    INSPECT_EVAL_MODEL environment variable, or default LLM.
    """
    return Task(
        dataset=[
            Sample(
                input="Just reply with Hello World",
                target="Hello World",
            )
        ],
        solver=[generate()],
        scorer=exact(),
    )
