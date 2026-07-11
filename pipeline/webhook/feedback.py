"""
feedback.py
Pure classifier for cooperative SMS replies to the weekly advisory (ELN-021 foundation).
No I/O — unit-testable. Maps a free-text reply (English / Tagalog) to a response code so
inbound replies can be stored in advisory_feedback and aggregated for impact reporting.

VENDORED COPY: this is intentionally duplicated from pipeline/scripts/feedback.py, not
imported via a relative/sys.path trick, because the webhook deploys as an isolated
service (Railway "Root Directory" = pipeline/webhook only copies that subdirectory into
the build — sibling folders like pipeline/scripts/ are never present in the container).
Keep in sync with the original if the classification logic changes; both are covered by
pipeline/tests/test_feedback.py against the original, and this copy is intentionally
identical.
"""

ACTED = "acted"
NOT_ACTED = "not_acted"
NEED_HELP = "need_help"
UNKNOWN = "unknown"

# Inbound reply that means "unsubscribe" → suppression (ELN-010), not feedback.
OPT_OUT_KEYWORDS = {"stop", "unsubscribe", "unsub", "tigil", "stopall", "wakasan"}


def classify_inbound(text: str) -> tuple[str, str | None]:
    """Route an inbound SMS reply for the webhook (ELN-010 + ELN-021).

    Returns ('opt_out', None) for an unsubscribe reply, otherwise
    ('feedback', <response_code>) using parse_feedback(). The first word is enough to
    catch "STOP", "STOP ALL", "TIGIL po", etc.
    """
    t = (text or "").strip().lower()
    first = t.split()[0] if t.split() else ""
    if t in OPT_OUT_KEYWORDS or first in OPT_OUT_KEYWORDS:
        return ("opt_out", None)
    return ("feedback", parse_feedback(text))

# Whole-token matches (checked against the full reply and its first word).
_ACTED_TOKENS = {"1", "yes", "y", "oo", "opo", "ok", "okay", "done", "ginawa", "tapos", "sige"}
_NOT_ACTED_TOKENS = {"2", "no", "n", "hindi", "wala", "di"}
_NEED_HELP_TOKENS = {"3", "help", "tulong", "?", "paano", "saklolo"}


def parse_feedback(text: str) -> str:
    """Classify a reply into acted / not_acted / need_help / unknown (case-insensitive).

    Recognizes simple numeric replies (1/2/3) and common English/Tagalog words. NEED_HELP
    takes precedence so a farmer asking for help is never miscounted as a plain yes/no.
    """
    if not text or not text.strip():
        return UNKNOWN
    t = text.strip().lower()
    tokens = t.split()
    first = tokens[0] if tokens else ""

    for candidate in (t, first):
        if candidate in _NEED_HELP_TOKENS:
            return NEED_HELP
        if candidate in _ACTED_TOKENS:
            return ACTED
        if candidate in _NOT_ACTED_TOKENS:
            return NOT_ACTED

    # Keyword-containment fallback for short phrases ("tulong po", "hindi pa", "ginawa na").
    if any(k in t for k in ("tulong", "help", "paano", "saklolo")):
        return NEED_HELP
    if any(k in t for k in ("ginawa", "done", "tapos")):
        return ACTED
    if any(k in t for k in ("hindi", "wala")):
        return NOT_ACTED
    return UNKNOWN
