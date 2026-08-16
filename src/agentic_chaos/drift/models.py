import hashlib
import math
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from difflib import unified_diff
from typing import Any, Literal

from pydantic import BaseModel, Field

_TOKEN_RE = re.compile(r"\w+")

DriftKind = Literal["prompt", "model", "output", "retrieval"]


def normalize_text(value: str) -> str:
    return " ".join(value.split()).strip()


def text_hash(value: str) -> str:
    return hashlib.sha256(normalize_text(value).encode("utf-8")).hexdigest()


def compute_text_distance(left: str, right: str) -> float:
    left_tokens = Counter(_TOKEN_RE.findall(normalize_text(left).lower()))
    right_tokens = Counter(_TOKEN_RE.findall(normalize_text(right).lower()))
    if not left_tokens and not right_tokens:
        return 0.0
    if not left_tokens or not right_tokens:
        return 1.0

    shared = set(left_tokens) | set(right_tokens)
    dot = sum(left_tokens[token] * right_tokens[token] for token in shared)
    left_norm = math.sqrt(sum(count * count for count in left_tokens.values()))
    right_norm = math.sqrt(sum(count * count for count in right_tokens.values()))
    if left_norm == 0.0 or right_norm == 0.0:
        return 1.0
    similarity = dot / (left_norm * right_norm)
    return max(0.0, min(1.0, 1.0 - similarity))


def compute_list_distance(left: list[str], right: list[str]) -> float:
    left_set = {normalize_text(item).lower() for item in left if normalize_text(item)}
    right_set = {normalize_text(item).lower() for item in right if normalize_text(item)}
    if not left_set and not right_set:
        return 0.0
    if not left_set or not right_set:
        return 1.0
    overlap = len(left_set & right_set)
    union = len(left_set | right_set)
    return 1.0 - (overlap / union)


def summarize_diff(left: str, right: str, *, max_lines: int = 12) -> list[str]:
    diff = list(
        unified_diff(
            left.splitlines(),
            right.splitlines(),
            fromfile="baseline",
            tofile="current",
            lineterm="",
        )
    )
    return diff[:max_lines]


class DriftSnapshot(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    prompt_text: str | None = None
    prompt_hash: str | None = None
    model_name: str | None = None
    model_fingerprint: str | None = None
    output_text: str | None = None
    output_hash: str | None = None
    retrieval_items: list[str] = Field(default_factory=list)
    retrieval_hash: str | None = None
    embedding_model: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def create(
        cls,
        *,
        name: str,
        prompt_text: str | None = None,
        model_name: str | None = None,
        model_fingerprint: str | None = None,
        output_text: str | None = None,
        retrieval_items: list[str] | None = None,
        embedding_model: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "DriftSnapshot":
        retrieval_items = retrieval_items or []
        return cls(
            name=name,
            prompt_text=prompt_text,
            prompt_hash=text_hash(prompt_text) if prompt_text is not None else None,
            model_name=model_name,
            model_fingerprint=model_fingerprint,
            output_text=output_text,
            output_hash=text_hash(output_text) if output_text is not None else None,
            retrieval_items=retrieval_items,
            retrieval_hash=text_hash("\n".join(retrieval_items)) if retrieval_items else None,
            embedding_model=embedding_model,
            metadata=metadata or {},
        )


class DriftFinding(BaseModel):
    kind: DriftKind
    changed: bool
    score: float | None = None
    threshold: float | None = None
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)


class DriftReport(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    compared_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    baseline_snapshot_id: str
    current_snapshot_id: str
    has_drift: bool
    findings: list[DriftFinding] = Field(default_factory=list)
    baseline: dict[str, Any] = Field(default_factory=dict)
    current: dict[str, Any] = Field(default_factory=dict)

    @staticmethod
    def _score_bucket(score: float | None, threshold: float | None) -> float | None:
        if score is None:
            return None
        if threshold is None or threshold <= 0:
            return round(score, 1)
        ratio = score / threshold
        # Bucket continuous signals coarsely so small run-to-run noise in
        # output/retrieval comparisons does not defeat cooldown suppression.
        return math.floor(ratio * 2) / 2

    @classmethod
    def _finding_fingerprint_payload(cls, finding: DriftFinding) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "kind": finding.kind,
            "changed": finding.changed,
        }
        if finding.kind in {"prompt", "model"}:
            payload["detail"] = finding.detail
            return payload

        payload["threshold"] = finding.threshold
        payload["score_bucket"] = cls._score_bucket(finding.score, finding.threshold)
        return payload

    def fingerprint(self) -> str:
        payload = {
            "has_drift": self.has_drift,
            "findings": [self._finding_fingerprint_payload(finding) for finding in self.findings],
        }
        return hashlib.sha256(str(payload).encode("utf-8")).hexdigest()


class DriftAlertState(BaseModel):
    last_report_fingerprint: str | None = None
    last_emitted_at: datetime | None = None
