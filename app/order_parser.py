
"""Parse Myanmar voice orders and expose three-tier diagnostics."""

import logging
import re

from .myanmar_text_normalizer import normalize_text
from .menu_matcher import MenuMatcher

logger = logging.getLogger("voice_order.parser")

COUNT_WORDS = {
    "တစ်": 1,
    "နှစ်": 2,
    "သုံး": 3,
    "လေး": 4,
    "ငါး": 5,
    "ခြောက်": 6,
    "ခုနစ်": 7,
    "ရှစ်": 8,
    "ကိုး": 9,
    "ဆယ်": 10,
}

UNITS = ("ခွက်", "ပွဲ", "ခု", "ချပ်", "လုံး", "ထုပ်", "စုံ")

COUNT_PATTERN = (
    r"(?:[0-9၀-၉]{1,2}|"
    + "|".join(
        re.escape(word)
        for word in sorted(COUNT_WORDS, key=len, reverse=True)
    )
    + r")"
)

UNIT_PATTERN = "|".join(map(re.escape, UNITS))

# Require an explicit unit to avoid treating သုံး inside
# သုံးထပ်သား as an order quantity.
NUMBER = re.compile(
    rf"(?P<number>{COUNT_PATTERN})"
    rf"\s*(?P<unit>{UNIT_PATTERN})"
)

AMBIGUOUS = re.compile(
    rf"{COUNT_PATTERN}\s*ခွဲ"
)

NOTES = (
    "ချိုပေါ့",
    "ချိုကျ",
    "ပုံမှန်",
    "အချိုလျှော့",
    "သကြားမထည့်",
    "အစပ်လျှော့",
    "အစပ်များ",
    "ပါဆယ်",
)


def _num(token):
    if token in COUNT_WORDS:
        return COUNT_WORDS[token]

    digits = token.translate(
        str.maketrans("၀၁၂၃၄၅၆၇၈၉", "0123456789")
    )

    return int(digits) if digits.isdecimal() else None


def _parse_qty(segment, item):
    """Parse explicit quantities without guessing."""

    if AMBIGUOUS.search(segment):
        return (
            None,
            "ခွဲ",
            ["Ambiguous ခွဲ: confirm quantity with waiter"],
        )

    matches = list(NUMBER.finditer(segment))

    if not matches:
        return (
            None,
            "",
            ["Missing explicit quantity and unit"],
        )

    if len(matches) > 1:
        return (
            None,
            "",
            ["Multiple quantities detected; confirm with waiter"],
        )

    match = matches[0]
    quantity = _num(match.group("number"))
    unit = match.group("unit")

    warnings = []

    if quantity is None or not 1 <= quantity <= 99:
        warnings.append("Quantity outside supported range")
        quantity = None

    if item and item.get("unit"):
        if unit != item["unit"]:
            warnings.append(
                f"Unit mismatch: heard {unit}, "
                f"menu expects {item['unit']}"
            )

    if item and item.get("unit_needs_review"):
        warnings.append("Menu unit has not been verified")

    return quantity, unit, warnings


class OrderParser:
    def __init__(self, menu_path=None, enable_semantic=False):
        self.matcher = MenuMatcher(
            menu_path,
            enable_semantic=enable_semantic,
        )

    @staticmethod
    def _line(
        phrase,
        match,
        qty,
        unit,
        warnings,
        note,
        candidates,
        tiers_attempted=None,
        match_tier=None,
    ):
        return {
            "phrase": phrase,
            "id": match["id"] if match else None,
            "name": match["name"] if match else None,
            "qty": qty,
            "unit": unit,
            "price": match["price"] if match else None,
            "note": note,
            "match_method": (
                match["method"] if match else None
            ),
            "match_tier": match_tier,
            "tiers_attempted": tiers_attempted or [],
            "warnings": list(dict.fromkeys(warnings)),
            "needs_review": bool(warnings or not match),
            "candidates": candidates,
        }

    def _search_phrase(self, phrase, quantity, unit):
        """Run matcher and retain its diagnostics."""

        result = self.matcher.search(phrase)

        candidates = result.get("candidates", [])
        attempted = result.get("tiers_attempted", [])

        # Compatibility with older MenuMatcher.search().
        if not attempted:
            tier = result.get("tier", "fuzzy")
            if tier == "exact":
                attempted = ["exact"]
            elif tier == "semantic":
                attempted = ["exact", "fuzzy", "semantic"]
            else:
                attempted = ["exact", "fuzzy"]

        match = None

        if (
            result.get("status") == "matched"
            and len(candidates) == 1
        ):
            match = candidates[0]

        item = (
            self.matcher.items.get(match["id"])
            if match else None
        )

        warnings = []

        if quantity is None:
            warnings.append("Quantity requires confirmation")

        if item and item.get("unit_needs_review"):
            warnings.append("Menu unit has not been verified")

        if item and unit and item.get("unit"):
            if unit != item["unit"]:
                warnings.append("Spoken unit does not match menu")

        if match is None:
            warnings.append("Menu item requires waiter confirmation")

        logger.info(
            "Phrase=%r | tiers=%s | candidates=%s",
            phrase,
            attempted,
            [
                (x["id"], x["method"], x["score"])
                for x in candidates
            ],
        )

        return self._line(
            phrase=phrase,
            match=match,
            qty=quantity,
            unit=unit,
            warnings=warnings,
            note="",
            candidates=candidates,
            tiers_attempted=attempted,
            match_tier=match["method"] if match else None,
        )

    def parse(self, text, table_no=None):
        cleaned = normalize_text(text)

        logger.info("Raw ASR: %s", text)
        logger.info("Normalized ASR: %s", cleaned)

        mentions = self.matcher.exact_mentions(cleaned)

        lines = []
        unmatched = []

        if mentions:
            prefix = cleaned[:mentions[0][0]].strip(" ၊။,")

            if prefix:
                unmatched.append(prefix)

            for index, (start, end, ids) in enumerate(mentions):
                next_start = (
                    mentions[index + 1][0]
                    if index + 1 < len(mentions)
                    else len(cleaned)
                )

                phrase = cleaned[start:end]
                tail = cleaned[end:next_start]

                match = (
                    self.matcher._entry(ids[0], "exact", 1.0)
                    if len(ids) == 1
                    else None
                )

                item = (
                    self.matcher.items[ids[0]]
                    if len(ids) == 1
                    else None
                )

                qty, unit, warnings = _parse_qty(tail, item)

                if len(ids) > 1:
                    warnings.append(
                        "Shared alias matches multiple menu items"
                    )

                if index == 0 and qty is None and prefix:
                    q, u, w = _parse_qty(prefix, item)

                    if q is not None:
                        qty, unit = q, u
                        warnings = w

                note = ", ".join(
                    n for n in NOTES if n in tail
                )

                candidates = [
                    self.matcher._entry(i, "exact", 1.0)
                    for i in ids
                ]

                logger.info(
                    "[TIER 1] %r -> %s",
                    phrase,
                    ids,
                )

                lines.append(
                    self._line(
                        phrase,
                        match,
                        qty,
                        unit,
                        warnings,
                        note,
                        candidates,
                        tiers_attempted=["exact"],
                        match_tier="exact" if match else None,
                    )
                )

                rest = NUMBER.sub(" ", tail)

                for n in NOTES:
                    rest = rest.replace(n, " ")

                rest = rest.strip(" ၊။, ")

                if rest:
                    unmatched.append(rest)

        else:
            cursor = 0

            for quantity_match in NUMBER.finditer(cleaned):
                phrase = cleaned[
                    cursor:quantity_match.start()
                ].strip(" ၊။, ")

                cursor = quantity_match.end()

                if not phrase:
                    continue

                qty, unit, _ = _parse_qty(
                    quantity_match.group(),
                    None,
                )

                lines.append(
                    self._search_phrase(phrase, qty, unit)
                )

            remainder = cleaned[cursor:].strip(" ၊။, ")

            if remainder:
                unmatched.append(remainder)

            if not lines and cleaned:
                lines.append(
                    self._search_phrase(cleaned, None, "")
                )

        return {
            "raw_text": text,
            "normalized_text": cleaned,
            "table_no": table_no,
            "items": lines,
            "unmatched_text": unmatched,
            "requires_confirmation": True,
            "semantic_enabled": self.matcher.enable_semantic,
            "semantic_error": getattr(
                self.matcher, "semantic_error", None
            ),
            "tiers_attempted": list(dict.fromkeys(
                tier
                for line in lines
                for tier in line["tiers_attempted"]
            )),
        }
