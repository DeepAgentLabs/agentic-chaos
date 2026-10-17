"""pytest-agentic-chaos: the ``@pytest.mark.chaos`` plugin shipped with agentic-chaos (v0.6).

Loaded automatically through the ``pytest11`` entry point. Disable it with
``pytest -p no:agentic_chaos``. See ``pytest_agentic_chaos.plugin``.
"""

from pytest_agentic_chaos.plugin import ChaosHandle, ChaosSpec

__all__ = ["ChaosHandle", "ChaosSpec"]
