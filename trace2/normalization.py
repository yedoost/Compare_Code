from __future__ import annotations

import re


_COMMENT_BLOCK_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_COMMENT_LINE_RE = re.compile(r"//.*?$", re.MULTILINE)


def normalize_content(text: str) -> str:
    without_block = _COMMENT_BLOCK_RE.sub(" ", text)
    without_line = _COMMENT_LINE_RE.sub(" ", without_block)
    normalized = re.sub(r"\s+", " ", without_line)
    return normalized.strip()
