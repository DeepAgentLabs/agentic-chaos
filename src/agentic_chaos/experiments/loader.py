"""Read experiment files (YAML, JSON or TOML) and validate them."""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from agentic_chaos.experiments.schema import (
    Experiment,
    ExperimentError,
    ExperimentIssue,
    compile_document,
)

YAML_SUFFIXES = (".yaml", ".yml")
SUFFIXES = (*YAML_SUFFIXES, ".json", ".toml")


@dataclass
class ValidationResult:
    """Outcome of validating one experiment source."""

    source: str
    issues: list[ExperimentIssue] = field(default_factory=list)
    experiment: Experiment | None = None

    @property
    def errors(self) -> list[ExperimentIssue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[ExperimentIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_json(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "ok": self.ok,
            "issues": [issue.as_json() for issue in self.issues],
        }


def read_document(path: str | Path) -> Any:
    """Parse an experiment file by suffix. YAML needs the `yaml` extra (PyYAML)."""
    source = Path(path)
    suffix = source.suffix.lower()
    if suffix not in SUFFIXES:
        raise ExperimentError(
            str(source),
            [
                ExperimentIssue(
                    "<file>", f"unsupported file type '{suffix}'; use {', '.join(SUFFIXES)}"
                )
            ],
        )
    try:
        text = source.read_text(encoding="utf-8")
    except OSError as exc:
        raise ExperimentError(str(source), [ExperimentIssue("<file>", str(exc))]) from exc
    try:
        if suffix in YAML_SUFFIXES:
            try:
                import yaml
            except ImportError as exc:
                raise ExperimentError(
                    str(source),
                    [
                        ExperimentIssue(
                            "<file>",
                            "YAML experiments need PyYAML: pip install 'agentic-chaos[yaml]' "
                            "(or write the experiment as .json / .toml)",
                        )
                    ],
                ) from exc
            try:
                return yaml.safe_load(text)
            except yaml.YAMLError as exc:
                mark = getattr(exc, "problem_mark", None)
                where = f"line {mark.line + 1}" if mark is not None else "<file>"
                problem = getattr(exc, "problem", None) or str(exc)
                raise ExperimentError(
                    str(source), [ExperimentIssue(where, f"invalid YAML: {problem}")]
                ) from exc
        if suffix == ".json":
            return json.loads(text)
        return tomllib.loads(text)
    except json.JSONDecodeError as exc:
        issue = ExperimentIssue(f"line {exc.lineno}", f"invalid JSON: {exc.msg}")
        raise ExperimentError(str(source), [issue]) from exc
    except tomllib.TOMLDecodeError as exc:
        raise ExperimentError(
            str(source), [ExperimentIssue("<file>", f"invalid TOML: {exc}")]
        ) from exc


def validate_experiment(
    source: str | Path | dict[str, Any] | Any,
    *,
    base_dir: str | Path | None = None,
    check_targets: bool = True,
) -> ValidationResult:
    """Validate an experiment file or parsed document without running anything.

    Relative target paths resolve against `base_dir`, which defaults to the
    experiment file's directory (or the working directory for a document).
    """
    if not isinstance(source, (str, Path)):
        label, data = "<document>", source
        directory = Path(base_dir) if base_dir is not None else Path.cwd()
    else:
        label = str(source)
        directory = Path(base_dir) if base_dir is not None else Path(source).resolve().parent
        try:
            data = read_document(source)
        except ExperimentError as exc:
            return ValidationResult(label, exc.issues)
    experiment, issues = compile_document(
        data, source=label, base_dir=directory, check_targets=check_targets
    )
    return ValidationResult(label, issues, experiment)


def load_experiment(
    source: str | Path | dict[str, Any],
    *,
    base_dir: str | Path | None = None,
    check_targets: bool = True,
) -> Experiment:
    """Validate and return an `Experiment`, raising `ExperimentError` on any error."""
    result = validate_experiment(source, base_dir=base_dir, check_targets=check_targets)
    if result.experiment is None:
        raise ExperimentError(result.source, result.errors or result.issues)
    return result.experiment
