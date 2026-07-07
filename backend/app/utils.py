import hashlib
import math
import subprocess
from typing import Any, Mapping, Sequence


def fingerprint(text: str) -> str:
    """Short, stable content hash of text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def cosine_similarity(u: Sequence[float], v: Sequence[float]) -> float:
    if len(u) != len(v) or not u:
        raise ValueError("cosine_similarity needs two equal-length, non-empty vectors")
    dot = sum(a * b for a, b in zip(u, v))
    norm_u = math.sqrt(sum(a * a for a in u))
    norm_v = math.sqrt(sum(b * b for b in v))
    if norm_u == 0 or norm_v == 0:
        raise ValueError("cosine_similarity is undefined for zero vectors")
    return dot / (norm_u * norm_v)


def git_provenance() -> dict[str, Any]:
    """{'commit', 'dirty'} for the working tree, or {} if git is unavailable."""
    try:
        run = lambda *a: subprocess.run(  # noqa: E731
            ["git", *a], capture_output=True, text=True, check=True
        ).stdout.strip()
        return {"commit": run("rev-parse", "HEAD"), "dirty": bool(run("status", "--porcelain"))}
    except Exception:  # noqa: BLE001 — best-effort
        return {}


def render_thread(
    thread: Sequence[Mapping[str, Any]],
    *,
    fmt: str = "{sender_name}: {body}",
    recent_n: int | None = None,
) -> str:
    """Join thread messages into one string; `fmt` is a str.format template over each
    message's keys, `recent_n` keeps only the trailing N messages."""
    messages = thread[-recent_n:] if recent_n is not None else thread
    return "\n".join(fmt.format(**message) for message in messages)
