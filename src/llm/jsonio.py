"""Pull a single JSON object out of a model reply."""

from __future__ import annotations

import json
import re


def parse_json_object(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, count=1, flags=re.IGNORECASE).strip()
        if text.endswith("```"):
            text = text[: -3].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in model output")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("JSON root must be an object")
    return data
