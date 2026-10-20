"""Turn a document into stable, citable chunks. Everything here is deterministic: chunk IDs and
offsets must not change between runs, because citations point at them."""
from __future__ import annotations

import re

_BLANK_RUN = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    """Unify line endings, strip trailing whitespace and collapse blank-line runs. Wording is untouched."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return _BLANK_RUN.sub("\n\n", text)
