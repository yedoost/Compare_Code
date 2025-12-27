from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable, List


@dataclass(frozen=True)
class FileFingerprint:
    sha256_normalized: str
    simhash64: str


@dataclass(frozen=True)
class ModuleFingerprint:
    sha256_normalized: str
    simhash64: str


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _token_hash(token: str) -> int:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def simhash64(tokens: Iterable[str]) -> str:
    vector: List[int] = [0] * 64
    for token in tokens:
        if not token:
            continue
        value = _token_hash(token)
        for i in range(64):
            bit = (value >> i) & 1
            vector[i] += 1 if bit else -1
    fingerprint = 0
    for i, score in enumerate(vector):
        if score >= 0:
            fingerprint |= 1 << i
    return f"{fingerprint:016x}"


def hamming_distance(a: str, b: str) -> int:
    value = int(a, 16) ^ int(b, 16)
    return value.bit_count()


def similarity_score(
    sha_a: str,
    sha_b: str,
    simhash_a: str,
    simhash_b: str,
) -> float:
    if sha_a == sha_b:
        return 1.0
    distance = hamming_distance(simhash_a, simhash_b)
    return max(0.0, 1.0 - (distance / 64.0))
