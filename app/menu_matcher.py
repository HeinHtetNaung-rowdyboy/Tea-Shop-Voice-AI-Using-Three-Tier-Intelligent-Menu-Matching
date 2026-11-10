
"""Three-tier menu candidate retrieval.

Tier 1: Exact menu aliases
Tier 2: RapidFuzz string similarity
Tier 3: FAISS semantic vector search

Similarity scores are NOT probabilities.
Uncertain matches require waiter confirmation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from rapidfuzz import fuzz, process

from .myanmar_text_normalizer import (
    match_key,
    normalize_text,
)
from .config import ROOT


logger = logging.getLogger("voice_order.matcher")


class MenuMatcher:

    def __init__(
        self,
        menu_path=None,
        enable_semantic=False,
    ):
        self.path = (
            Path(menu_path)
            if menu_path
            else ROOT / "data" / "menu.json"
        )

        data = json.loads(
            self.path.read_text(encoding="utf-8")
        )

        self.menu = (
            data["items"]
            if isinstance(data, dict) and "items" in data
            else data
        )

        # Only index available, named products.
        self.menu = [
            item
            for item in self.menu
            if item.get("available", True)
            and item.get("name")
        ]

        self.items = {
            str(item["id"]): item
            for item in self.menu
        }

        # Normalized alias -> set of POS item IDs.
        # A shared alias can identify multiple products.
        self.aliases = {}

        for item in self.menu:
            phrases = [
                item["name"],
                *(item.get("aliases") or []),
            ]

            for phrase in phrases:
                key = match_key(phrase)

                if key:
                    self.aliases.setdefault(
                        key, set()
                    ).add(str(item["id"]))

        self.alias_keys = list(self.aliases.keys())

        self.enable_semantic = enable_semantic
        self._semantic = None
        self.semantic_error = None

        logger.info(
            "[MENU] Loaded %d items and %d unique aliases",
            len(self.menu),
            len(self.aliases),
        )

    def _entry(self, item_id, method, score):
        """Build one menu candidate."""

        item_id = str(item_id)
        item = self.items[item_id]

        return {
            "id": item_id,
            "name": item["name"],
            "price": int(item["price"]),
            "unit": item.get("unit") or "",
            "unit_needs_review": item.get(
                "unit_needs_review", False
            ),
            "method": method,
            "score": round(float(score), 4),
        }

    def candidates(
        self,
        phrase: str,
        top_k: int = 4,
    ):
        """Run Tier 1 exact, then Tier 2 fuzzy matching."""

        top_k = max(1, int(top_k))

        query = match_key(normalize_text(phrase))

        logger.info(
            "[MATCH] Original phrase: %s",
            phrase,
        )

        logger.info(
            "[MATCH] Normalized query: %s",
            query,
        )

        if not query:
            return []

        # ===========================================
        # TIER 1: EXACT ALIAS MATCHING
        # ===========================================

        logger.info("[TIER 1] Checking exact aliases")

        exact_ids = self.aliases.get(query, set())

        if exact_ids:
            result = [
                self._entry(
                    item_id,
                    "exact",
                    1.0,
                )
                for item_id in sorted(exact_ids)
            ]

            for item in result:
                logger.info(
                    "[TIER 1] %s | %s | exact",
                    item["id"],
                    item["name"],
                )

            if len(result) > 1:
                logger.warning(
                    "[TIER 1] Shared alias: %d items",
                    len(result),
                )

            # Return all exact collisions for review.
            return result

        logger.info(
            "[TIER 1] No exact match found"
        )

        # ===========================================
        # TIER 2: RAPIDFUZZ MATCHING
        # ===========================================

        logger.info(
            "[TIER 2] Starting RapidFuzz search"
        )

        results = process.extract(
            query,
            self.alias_keys,
            scorer=fuzz.ratio,
            score_cutoff=48,
            limit=None,
        )

        scored = {}

        for alias, score, _ in results:
            item_ids = self.aliases[alias]

            for item_id in item_ids:
                normalized_score = score / 100.0

                scored[item_id] = max(
                    scored.get(item_id, 0.0),
                    normalized_score,
                )

        candidates = [
            self._entry(
                item_id,
                "fuzzy",
                score,
            )
            for item_id, score in scored.items()
        ]

        candidates.sort(
            key=lambda item: (
                -item["score"],
                item["id"],
            )
        )

        logger.info(
            "[TIER 2] %d candidate products",
            len(candidates),
        )

        for item in candidates[:top_k]:
            logger.info(
                "[TIER 2] %s | %s | %.2f%%",
                item["id"],
                item["name"],
                item["score"] * 100,
            )

        return candidates[:top_k]

    def search(
        self,
        phrase: str,
        top_k: int = 4,
    ):
        """Run the three tiers and report diagnostics."""

        top_k = max(1, int(top_k))

        logger.info(
            "========== VOICE MENU MATCHING =========="
        )

        logger.info(
            "Input phrase: %s",
            phrase,
        )

        # Clear previous request's error.
        self.semantic_error = None

        # Tier 1 and Tier 2 happen in candidates().
        found = self.candidates(phrase, top_k)

        # ===========================================
        # TIER 1: EXACT MATCH FOUND
        # ===========================================

        if found and found[0]["method"] == "exact":

            status = (
                "matched"
                if len(found) == 1
                else "needs_confirmation"
            )

            logger.info(
                "[TIER 1] Status: %s",
                status,
            )

            logger.info(
                "Tiers attempted: ['exact']"
            )

            return {
                "status": status,
                "candidates": found,
                "tier": "exact",
                "tiers_attempted": ["exact"],
                "semantic_error": None,
            }

        # ===========================================
        # TIER 2: FUZZY CANDIDATES
        # ===========================================

        attempted = ["exact", "fuzzy"]

        logger.info(
            "[TIER 1] No exact alias match"
        )

        logger.info(
            "[TIER 2] Evaluating fuzzy results"
        )

        top_score = (
            found[0]["score"]
            if found
            else 0.0
        )

        second_score = (
            found[1]["score"]
            if len(found) > 1
            else 0.0
        )

        score_gap = top_score - second_score

        strong_fuzzy = bool(
            found
            and top_score >= 0.93
            and (
                len(found) == 1
                or score_gap >= 0.12
            )
        )

        logger.info(
            "[TIER 2] Top score: %.4f",
            top_score,
        )

        logger.info(
            "[TIER 2] Score gap: %.4f",
            score_gap,
        )

        if strong_fuzzy:
            logger.info(
                "[TIER 2] Strong candidate; waiter review required"
            )

            return {
                "status": "needs_confirmation",
                "candidates": found,
                "tier": "fuzzy",
                "tiers_attempted": attempted,
                "semantic_error": None,
            }

        # ===========================================
        # TIER 3: FAISS SEMANTIC MATCHING
        # ===========================================

        semantic_succeeded = False
        semantic_count = 0

        if self.enable_semantic:
            attempted.append("semantic")

            logger.info(
                "[TIER 3] Starting FAISS search"
            )

            try:
                if self._semantic is None:
                    from .semantic_matcher import (
                        SemanticMatcher
                    )

                    logger.info(
                        "[TIER 3] Loading multilingual MiniLM"
                    )

                    self._semantic = SemanticMatcher(
                        self.menu
                    )

                semantic_results = self._semantic.search(
                    phrase,
                    top_k=top_k,
                )

                semantic_succeeded = True

                existing_ids = {
                    item["id"]
                    for item in found
                }

                for item in semantic_results:
                    item_id = str(item["id"])

                    logger.info(
                        "[TIER 3] %s | score %.4f",
                        item_id,
                        float(item["score"]),
                    )

                    if item_id not in self.items:
                        logger.warning(
                            "[TIER 3] Unknown ID: %s",
                            item_id,
                        )
                        continue

                    if item_id not in existing_ids:
                        found.append(
                            self._entry(
                                item_id,
                                "semantic",
                                item["score"],
                            )
                        )

                        existing_ids.add(item_id)
                        semantic_count += 1

                logger.info(
                    "[TIER 3] %d new candidates added",
                    semantic_count,
                )

            except Exception as exc:
                self.semantic_error = str(exc)

                logger.exception(
                    "[TIER 3] FAISS failed: %s",
                    exc,
                )

        else:
            logger.info(
                "[TIER 3] Disabled"
            )

        # Keep fuzzy and semantic candidate scores separate.
        # They use different similarity measurements.
        status = (
            "needs_confirmation"
            if found
            else "not_found"
        )

        # 'tier' identifies the last successful search
        # stage, not necessarily the winning candidate.
        last_tier = (
            "semantic"
            if semantic_succeeded
            else "fuzzy"
        )

        logger.info(
            "[MATCH] Final status: %s",
            status,
        )

        logger.info(
            "[MATCH] Tiers attempted: %s",
            attempted,
        )

        logger.info(
            "[MATCH] Candidates returned: %d",
            len(found),
        )

        logger.info(
            "========================================="
        )

        return {
            "status": status,
            "candidates": found[
                :max(top_k, 4) * 2
            ],
            "tier": last_tier,
            "tiers_attempted": attempted,
            "semantic_error": self.semantic_error,
        }

    def exact_mentions(self, text):
        """Find longest nonoverlapping exact menu mentions."""

        key = match_key(text)

        # Map normalized non-space positions to source.
        nonspaces = [
            (i, ch)
            for i, ch in enumerate(text)
            if not ch.isspace()
        ]

        # Unicode normalization may change offsets.
        if len(key) != len(nonspaces):
            logger.warning(
                "[TIER 1] Cannot safely map text offsets"
            )
            return []

        hits = []

        for alias, ids in self.aliases.items():
            start = 0

            while True:
                pos = key.find(alias, start)

                if pos < 0:
                    break

                if pos + len(alias) <= len(nonspaces):
                    hits.append(
                        (
                            nonspaces[pos][0],
                            nonspaces[
                                pos + len(alias) - 1
                            ][0] + 1,
                            ids,
                            len(alias),
                        )
                    )

                start = pos + 1

        # Prefer longer aliases.
        hits.sort(
            key=lambda hit: (
                -hit[3],
                hit[0],
            )
        )

        result = []

        for start, end, ids, _ in hits:
            if any(
                start < selected[1]
                and end > selected[0]
                for selected in result
            ):
                continue

            result.append(
                (
                    start,
                    end,
                    sorted(ids),
                )
            )

        result.sort()

        for start, end, ids in result:
            logger.info(
                "[TIER 1] Exact mention: %r -> %s",
                text[start:end],
                ids,
            )

        return result
