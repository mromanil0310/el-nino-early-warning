"""
advisory.py
Pure parser for the labelled advisory text returned by Claude. No I/O — unit-testable.

The model is prompted to emit:
    ADVISORY_EN: <english, may span multiple lines>
    ADVISORY_TL: <tagalog, may span multiple lines>
    SMS_TEXT: <one line>

The previous line-by-line parser kept only the FIRST line of each value, silently
truncating multi-line advisories. This captures each value in full — everything from
its label to the next recognized label (or end of text).
"""

import re

ADVISORY_KEYS = ("ADVISORY_EN", "ADVISORY_TL", "SMS_TEXT")


def parse_advisory(raw: str, keys: tuple[str, ...] = ADVISORY_KEYS) -> dict[str, str]:
    """Parse labelled advisory text into ``{KEY: value}``, capturing multi-line values.

    Labels are matched at the start of a line, case-insensitively, tolerating a leading
    bullet or number (e.g. ``1. ADVISORY_EN:``). Internal whitespace/newlines in a value
    are collapsed to single spaces. Missing keys are simply absent from the result.
    """
    if not raw:
        return {}
    label_re = re.compile(
        r"^[ \t]*[-*\d.\)\s]*(" + "|".join(re.escape(k) for k in keys) + r")[ \t]*[:\-][ \t]*",
        re.IGNORECASE | re.MULTILINE,
    )
    matches = list(label_re.finditer(raw))
    result: dict[str, str] = {}
    for i, m in enumerate(matches):
        key = m.group(1).upper()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        value = re.sub(r"\s+", " ", raw[start:end]).strip()
        if value and key not in result:
            result[key] = value
    return result
