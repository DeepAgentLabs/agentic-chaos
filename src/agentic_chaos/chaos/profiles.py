"""Strict named TOML profiles with optional per-fault constructor parameters."""

import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from agentic_chaos.chaos.faults import FAULT_REGISTRY, BaseFault


def load_profile(name: str, path: str | Path = "chaos.toml") -> list[BaseFault]:
    """Load fresh fault instances; never reuse burst/decay state between runs.

    profiles.NAME accepts faults, probability, seed, and parameters.NAME tables.
    Unknown fields and invalid constructor parameters fail before executing a script.
    """
    with Path(path).open("rb") as file:
        data = tomllib.load(file)
    profiles = data.get("profiles", {})
    if not isinstance(profiles, dict) or name not in profiles:
        raise ValueError(f"Unknown chaos profile '{name}'")
    profile = profiles[name]
    if not isinstance(profile, dict) or set(profile) - {
        "faults",
        "probability",
        "seed",
        "parameters",
    }:
        raise ValueError("Profile accepts only faults, probability, seed, and parameters")
    names = profile.get("faults")
    if not isinstance(names, list) or not names or not all(isinstance(n, str) for n in names):
        raise ValueError("Profile faults must be a non-empty list of fault names")
    if len(set(names)) != len(names):
        raise ValueError("Profile contains duplicate fault names")
    parameters = profile.get("parameters", {})
    if not isinstance(parameters, dict) or set(parameters) - set(names):
        raise ValueError("Profile parameters must reference configured fault names")
    probability = profile.get("probability", 1.0)
    if isinstance(probability, bool) or not isinstance(probability, (int, float)):
        raise ValueError("Profile probability must be a number")
    seed = profile.get("seed")
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
        raise ValueError("Profile seed must be an integer")
    faults = []
    for fault_name in names:
        if fault_name not in FAULT_REGISTRY:
            raise ValueError(f"Unknown fault '{fault_name}'")
        options: Any = parameters.get(fault_name, {})
        if not isinstance(options, dict):
            raise ValueError(f"Parameters for '{fault_name}' must be a table")
        try:
            fault = FAULT_REGISTRY[fault_name](
                **{"probability": probability, "seed": seed, **options}
            )
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid profile parameters for '{fault_name}': {exc}") from exc
        faults.append(fault)
    return faults
