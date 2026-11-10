
"""Conservative Myanmar ASR cleanup.

Removes Raj-0 metadata, corrects verified ASR errors,
and removes trailing filler phrases.

Does not automatically change meaningful quantity words.
"""

import re
import unicodedata


# Only use corrections verified with actual recordings.
KNOWN_ERRORS = {
    "အလက်ဖက်ရည်": "လက်ဖက်ရည်",
    "အလာတာ": "ပလာတာ",
}

FILLERS = (
    "လုပ်ပေးပါ",
    "ပေး ပါ",
    "ပေးပါ",
    "ကျေးဇူးပါ",
)


def clean_raj_asr_text(text: str) -> str:
    """Remove Raj-0 metadata and ASR special tokens."""

    if not text:
        return ""

    text = unicodedata.normalize("NFC", text)

    # Remove leading language metadata.
    # Examples:
    # language None<asr_text>
    # language my-MM<asr_text>
    # language my <|asr_text|>
    text = re.sub(
        r"^\s*language\s+"
        r"(?:None|[a-zA-Z_-]+)\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Remove only known ASR marker variants.
    text = re.sub(
        r"<(?:\|asr_text\||asr_text)>",
        "",
        text,
        flags=re.IGNORECASE,
    )

    return text.strip()


def normalize_text(
    text: str,
    *,
    correct_errors: bool = True,
) -> str:
    """Normalize Raj-0 Myanmar transcription."""

    # Step 1: Remove Raj metadata first.
    text = clean_raj_asr_text(text)

    # Step 2: Normalize Myanmar Unicode.
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[\u200b\ufeff]", "", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Step 3: Apply verified ASR corrections.
    if correct_errors:
        for wrong, right in sorted(
            KNOWN_ERRORS.items(),
            key=lambda x: -len(x[0]),
        ):
            text = text.replace(wrong, right)

    # Step 4: Remove trailing punctuation.
    text = re.sub(r"[၊။,.!?\s]+$", "", text)

    # Step 5: Remove filler phrases only at the end.
    # Never remove these words inside menu names.
    for filler in sorted(
        FILLERS,
        key=len,
        reverse=True,
    ):
        text = re.sub(
            r"(?:\s|^|[၊။,])"
            + re.escape(filler)
            + r"$",
            "",
            text,
        ).strip()

        text = re.sub(r"[၊။,.!?\s]+$", "", text)

    return re.sub(r"\s+", " ", text).strip(
        " ၊။,.!?"
    )


def match_key(text: str) -> str:
    """Build a key for exact alias matching."""

    text = unicodedata.normalize("NFC", text or "")

    return re.sub(r"\s+", "", text).casefold()
