"""Optional adapters to other libraries.

Nothing under `agentic_chaos.integrations` is imported by `agentic_chaos`'s
core (`chaos_call`, `chaos_session`, the CLI) or by this package's
`__init__.py` -- import a submodule explicitly to opt in, and install its
extra (e.g. `pip install agentic-chaos[agenticlens]`) to satisfy its
dependency.
"""
