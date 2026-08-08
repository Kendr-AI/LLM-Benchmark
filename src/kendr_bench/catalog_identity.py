"""Canonical identity helpers for captured Kendr model catalogs."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence


def catalog_sha256(catalog: Sequence[Mapping[str, Any]]) -> str:
    """Hash a catalog using the repository's canonical JSON representation.

    Entry order remains significant because the captured API array is part of
    the snapshot. Object keys are sorted and insignificant whitespace is
    removed so formatting changes do not alter the identity.
    """

    encoded = json.dumps(
        [dict(model) for model in catalog],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
