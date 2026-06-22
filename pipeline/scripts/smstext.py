"""
smstext.py
Pure, encoding-aware SMS text formatting (GSM-7 vs UCS-2). No I/O — unit-testable.

A message is GSM-7 (160 chars single / 153 per concatenated segment) only if EVERY
character is in the GSM 03.38 alphabet. A single non-GSM-7 character forces the whole
message to UCS-2 (70 single / 67 per segment). So naive fixed-length truncation
(e.g. ``sms_text[:130]``) both overruns a segment — extra carrier cost beyond the
₱0.65 budget — and can cut mid-word.

Note: ñ/Ñ and à/ä/ö/ü/è/é ARE in GSM-7, so "El Niño" stays GSM-7. The real UCS-2
triggers in this app's content are acute-accent vowels (á/í/ó/ú), the peso sign ₱,
em-dashes (—), and curly quotes (" " ' ') — all common in generated advisory text.
"""

# GSM 03.38 basic alphabet — each character is one septet.
GSM7_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
# GSM 03.38 extension table — each of these costs two septets.
GSM7_EXTENSION = set("^{}\\[~]|€")

GSM7_SINGLE, GSM7_MULTI = 160, 153
UCS2_SINGLE, UCS2_MULTI = 70, 67


def is_gsm7(text: str) -> bool:
    return all(c in GSM7_BASIC or c in GSM7_EXTENSION for c in text)


def sms_encoding(text: str) -> str:
    return "GSM-7" if is_gsm7(text) else "UCS-2"


def sms_length(text: str) -> int:
    """Billable length in the message's own encoding (GSM-7 extension chars count 2)."""
    if is_gsm7(text):
        return sum(2 if c in GSM7_EXTENSION else 1 for c in text)
    return len(text)


def sms_segments(text: str) -> int:
    single, multi = (GSM7_SINGLE, GSM7_MULTI) if is_gsm7(text) else (UCS2_SINGLE, UCS2_MULTI)
    n = sms_length(text)
    return 1 if n <= single else -(-n // multi)  # ceil division


def fit_sms(body: str, suffix: str = "", ellipsis: str = "...") -> str:
    """Return ``body + suffix`` trimmed to ONE SMS segment for its encoding.

    Only ``body`` is trimmed (the ``suffix``, e.g. " -ELNINO", is always preserved);
    trimming prefers a word boundary and appends ``ellipsis`` when anything was cut.
    """
    full = body + suffix
    if sms_segments(full) <= 1:
        return full
    single = GSM7_SINGLE if is_gsm7(full) else UCS2_SINGLE
    budget = max(0, single - sms_length(suffix) - len(ellipsis))
    trimmed = body[:budget]
    while trimmed and sms_length(trimmed) > budget:
        trimmed = trimmed[:-1]
    cut = trimmed.rstrip().rfind(" ")
    if cut >= budget // 2:
        trimmed = trimmed[:cut]
    return trimmed.rstrip() + ellipsis + suffix
