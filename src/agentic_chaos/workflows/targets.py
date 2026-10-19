"""Resolve workflow targets from text and check them without executing them.

A target spec is one of:

- ``app.py`` -- a script, run with ``runpy`` as ``__main__`` on every invocation
  (the same way ``chaos run`` runs it); a non-zero ``sys.exit()`` is a failure
- ``app.py:handle`` -- a function defined at the top level of a file
- ``package.module:handle`` -- a function in an importable module

Relative file paths resolve against ``base_dir`` (an experiment's directory).
"""

import ast
import importlib
import importlib.util
import runpy
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any


class ScriptExitError(RuntimeError):
    """A script target called ``sys.exit()`` with a non-zero code."""

    def __init__(self, script: Path, code: object) -> None:
        super().__init__(f"{script} exited with code {code!r}")
        self.code = code


def _split(spec: str) -> tuple[str, str | None]:
    if not isinstance(spec, str) or not spec.strip():
        raise ValueError("target must be a non-empty string")
    spec = spec.strip()
    location, sep, attr = spec.rpartition(":")
    # Keep Windows drive letters (C:\app.py) and plain scripts intact.
    if not sep or not attr or (len(location) == 1 and location.isalpha()):
        return spec, None
    if not attr.isidentifier():
        raise ValueError(f"target function '{attr}' is not a valid Python identifier")
    return location, attr


def _is_file(location: str) -> bool:
    return location.endswith(".py") or "/" in location or "\\" in location


def _path(location: str, base_dir: Path | None) -> Path:
    path = Path(location)
    if not path.is_absolute() and base_dir is not None:
        path = base_dir / path
    return path


def script_target(script: Path) -> Callable[[], None]:
    """A no-argument callable that runs `script` as ``__main__``."""

    def run() -> None:
        try:
            runpy.run_path(str(script), run_name="__main__")
        except SystemExit as exc:
            if exc.code not in (None, 0):
                raise ScriptExitError(script, exc.code) from exc

    run.__name__ = script.stem
    return run


def resolve_target(spec: str, base_dir: Path | None = None) -> Callable[..., Any]:
    """Import and return the callable a target spec names (this may run module code)."""
    location, attr = _split(spec)
    if _is_file(location):
        path = _path(location, base_dir)
        if not path.is_file():
            raise ValueError(f"target file not found: {path}")
        if attr is None:
            return script_target(path)
        # One module per file, so a step and a health check share its state.
        module_name = f"_agentic_chaos_target_{abs(hash(str(path.resolve())))}"
        module = sys.modules.get(module_name)
        if module is None:
            module_spec = importlib.util.spec_from_file_location(module_name, path)
            if module_spec is None or module_spec.loader is None:
                raise ValueError(f"cannot load target file: {path}")
            module = importlib.util.module_from_spec(module_spec)
            sys.modules[module_name] = module
            try:
                module_spec.loader.exec_module(module)
            except BaseException:
                sys.modules.pop(module_name, None)
                raise
    else:
        if attr is None:
            raise ValueError("module targets need a function: use 'package.module:function'")
        module = importlib.import_module(location)
    target = getattr(module, attr, None)
    if not callable(target):
        raise ValueError(f"target '{spec}' is not a callable")
    return target  # type: ignore[no-any-return]


def _top_level_names(node: ast.stmt) -> list[str]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [node.name]
    if isinstance(node, ast.Assign):
        return [target.id for target in node.targets if isinstance(target, ast.Name)]
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return [node.target.id]
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return [alias.asname or alias.name.split(".")[0] for alias in node.names]
    return []


def _defines(source: str, filename: str, attr: str) -> bool:
    tree = ast.parse(source, filename=filename)
    return any(attr in _top_level_names(node) for node in tree.body)


def check_target(spec: str, base_dir: Path | None = None) -> str | None:
    """Return a problem with `spec`, or None. Never executes target code.

    Files are parsed, not imported. Module targets are located with
    ``importlib.util.find_spec``, which imports parent packages of a dotted
    name (as any import would) but not the module itself.
    """
    try:
        location, attr = _split(spec)
    except ValueError as exc:
        return str(exc)
    if _is_file(location):
        path = _path(location, base_dir)
        if not path.is_file():
            return f"target file not found: {path}"
        source_path: Path | None = path
    else:
        if attr is None:
            return "module targets need a function: use 'package.module:function'"
        try:
            found = importlib.util.find_spec(location)
        except (ImportError, ValueError) as exc:
            return f"target module '{location}' cannot be located: {exc}"
        if found is None:
            return f"target module '{location}' is not importable"
        origin = found.origin
        source_path = Path(origin) if origin and origin.endswith(".py") else None
    if source_path is None:
        return None  # extension or namespace module: nothing to parse statically
    try:
        source = source_path.read_text(encoding="utf-8")
        if attr is None:
            compile(source, str(source_path), "exec", dont_inherit=True)
            return None
        if not _defines(source, str(source_path), attr):
            return f"'{attr}' is not defined at the top level of {source_path}"
    except SyntaxError as exc:
        return f"target has a syntax error: {exc.msg} ({source_path}:{exc.lineno})"
    except (OSError, UnicodeDecodeError) as exc:
        return f"cannot read target {source_path}: {exc}"
    return None
