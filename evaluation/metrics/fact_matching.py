"""
evaluation/metrics/fact_matching.py — Deterministic scoring for Experiment 1.

NO LLM CALLS in this module.  All scoring is deterministic and reproducible.

Metrics
-------
factual_accuracy
    Proportion of expected_facts that are "matched" in the generated answer.
    Matching uses a two-tier approach:

    Tier 1 (substring match): the expected fact, normalised to lowercase with
    punctuation stripped, appears as a substring of the normalised answer.
    Tier 1 match is counted as a full match (confidence = 1.0).

    Tier 2 (fuzzy match): if Tier 1 fails, we use token overlap: the Jaccard
    similarity of the stemmed token sets of fact and answer-sentence is ≥ the
    FUZZY_THRESHOLD (default 0.35).  Tier 2 match contributes to
    factual_accuracy but sets needs_human_review=True for that item.

    factual_accuracy = (Tier1_matches + Tier2_matches) / len(expected_facts)
    Range: [0, 1].  0 → no facts found.  1 → all facts found.

hallucinated  (bool — approximation, NOT a perfect judge)
    A HEURISTIC flag, not a ground-truth label.  It is set True when the
    answer contains a specific-looking numerical or proper-noun claim that:
      (a) matches a regex pattern for a "specific claim" (number, CGPA,
          salary, percentage, company name pattern), AND
      (b) that claim is NOT present in any expected_fact AND
          NOT present in any of the retrieved source text (for RAG answers).
    This is an approximation.  It will produce false positives (flagging
    genuine but unexpected facts) and false negatives (missing hallucinations
    that don't match the regex patterns).  ALWAYS report the
    pct_needs_human_review in results and acknowledge this limitation.

citation_precision  (float | None — RAG answers only)
    Proportion of cited source doc IDs that are in gold_source_doc_ids.
    None for vanilla answers (no citations).

needs_human_review  (bool)
    Set True whenever:
      - At least one expected_fact was matched only by Tier 2 (fuzzy), OR
      - The hallucination heuristic fires with a match count > 0 but the
        number of hallucinated claims is ≤ HALLUCINATION_AMBIGUITY_THRESHOLD
        (i.e., it is unclear whether the model hallucinated or simply stated
        a valid fact not in the expected_facts list).
    This flag is surfaced in every results CSV row and must not be silently
    resolved.

Documented limitations (required by master plan Section 7)
-----------------------------------------------------------
- The hallucination heuristic is pattern-based and NOT equivalent to human
  judgment.  It will miss creative/syntactic hallucinations and may falsely
  flag valid answers.
- Tier 2 fuzzy matching may credit the model for partially overlapping facts
  that a human would judge as wrong.
- citation_precision only measures whether the right source was cited, not
  whether the cited text actually supports the answer.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Sequence


# ---------------------------------------------------------------------------
# Configuration constants (documented thresholds)
# ---------------------------------------------------------------------------

FUZZY_THRESHOLD: float = 0.35
"""Minimum Jaccard token-set similarity for a Tier 2 (fuzzy) match."""

HALLUCINATION_AMBIGUITY_THRESHOLD: int = 1
"""
If the heuristic detects ≤ this many suspicious claims and at least one
expected_fact was matched, we flag needs_human_review rather than hallucinated,
since there's ambiguity about whether those claims are errors or valid extras.
"""

# Regex for "specific claims" — numeric values or known entity patterns that
# look like verifiable assertions.  False-positive-prone by design (conservative).
_SPECIFIC_CLAIM_PATTERN = re.compile(
    r"""
    \b(
        \d+\.?\d*\s*(?:lpa|lakh|crore|%|cgpa|gpa|  # money / scores / percentages
            round[s]?|year[s]?|month[s]?|week[s]?|  # counts
            hrs?|hour[s]?|minute[s]?)                # durations
    |
        [A-Z][a-zA-Z]+(?:Tech|Fin|Corp|Labs?|Systems?|Solutions?|Robotics?)
                                                      # company-name-like tokens
    )
    """,
    re.VERBOSE | re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Text normalisation helpers
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """Lower-case, strip accents, collapse whitespace, remove punctuation."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "may", "might", "must", "can", "could", "to", "of", "in",
    "on", "at", "by", "for", "with", "about", "as", "and", "or", "but",
    "if", "than", "that", "this", "it", "its", "from", "up", "out", "not",
}


def _token_set(text: str) -> set[str]:
    """Normalised token set with stopwords removed."""
    return {t for t in _normalise(text).split() if t not in _STOPWORDS and len(t) > 1}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class FactMatchResult:
    """
    Per-question scoring result.

    All fields are written verbatim to results/experiment_1_raw.csv.
    """
    factual_accuracy: float          # [0, 1]
    hallucinated: bool               # heuristic approximation (see module docstring)
    citation_precision: float | None # None for vanilla answers
    needs_human_review: bool
    # Diagnostic fields (not in primary CSV but logged for transparency)
    n_facts: int
    tier1_matches: int
    tier2_matches: int
    suspicious_claims: list[str]
    matched_facts: list[str]
    unmatched_facts: list[str]

    def to_csv_dict(self) -> dict:
        return {
            "factual_accuracy": round(self.factual_accuracy, 4),
            "hallucinated": self.hallucinated,
            "citation_precision": (
                round(self.citation_precision, 4)
                if self.citation_precision is not None
                else ""
            ),
            "needs_human_review": self.needs_human_review,
        }


# ---------------------------------------------------------------------------
# Core scoring
# ---------------------------------------------------------------------------

def score(
    answer: str,
    expected_facts: Sequence[str],
    gold_source_doc_ids: Sequence[str],
    cited_doc_ids: Sequence[str] | None = None,
    source_context: str = "",
) -> FactMatchResult:
    """
    Score a generated answer deterministically.

    Args:
        answer:               Generated answer text.
        expected_facts:       List of expected fact strings from the dataset.
        gold_source_doc_ids:  List of gold source document IDs.
        cited_doc_ids:        List of source doc IDs cited in the answer
                              (RAG answers only; None → no citation_precision).
        source_context:       Full retrieved context text (used by hallucination
                              heuristic to check whether a suspicious claim was
                              actually in the retrieved passages).

    Returns:
        FactMatchResult with all scores and diagnostic fields.
    """
    norm_answer = _normalise(answer)
    answer_tokens = _token_set(answer)

    tier1_matches = 0
    tier2_matches = 0
    matched_facts: list[str] = []
    unmatched_facts: list[str] = []
    fuzzy_fired = False

    for fact in expected_facts:
        norm_fact = _normalise(fact)
        if norm_fact in norm_answer:
            # Tier 1: substring match
            tier1_matches += 1
            matched_facts.append(fact)
        else:
            # Tier 2: Jaccard token similarity
            fact_tokens = _token_set(fact)
            sim = _jaccard(fact_tokens, answer_tokens)
            if sim >= FUZZY_THRESHOLD:
                tier2_matches += 1
                matched_facts.append(fact)
                fuzzy_fired = True
            else:
                unmatched_facts.append(fact)

    n_facts = len(expected_facts)
    factual_accuracy = (tier1_matches + tier2_matches) / n_facts if n_facts > 0 else 0.0

    # --- Hallucination heuristic ---
    suspicious_claims: list[str] = []
    norm_expected_blob = _normalise(" ".join(expected_facts))
    norm_context = _normalise(source_context)

    for match in _SPECIFIC_CLAIM_PATTERN.finditer(norm_answer):
        claim = match.group(0).strip()
        # Not in expected facts AND not in retrieved context → suspicious
        if claim not in norm_expected_blob and claim not in norm_context:
            suspicious_claims.append(claim)

    n_suspicious = len(suspicious_claims)
    hallucinated = False
    needs_human_review = fuzzy_fired  # Tier 2 match always triggers review

    if n_suspicious > HALLUCINATION_AMBIGUITY_THRESHOLD:
        # More than the ambiguity threshold → call it hallucinated
        hallucinated = True
    elif n_suspicious > 0:
        # In the ambiguous zone → flag for human review, not auto-labelled
        needs_human_review = True

    # --- Citation precision ---
    citation_precision: float | None = None
    if cited_doc_ids is not None:
        gold_set = set(gold_source_doc_ids)
        cited_set = set(cited_doc_ids)
        citation_precision = (
            len(cited_set & gold_set) / len(cited_set) if cited_set else 0.0
        )

    return FactMatchResult(
        factual_accuracy=factual_accuracy,
        hallucinated=hallucinated,
        citation_precision=citation_precision,
        needs_human_review=needs_human_review,
        n_facts=n_facts,
        tier1_matches=tier1_matches,
        tier2_matches=tier2_matches,
        suspicious_claims=suspicious_claims,
        matched_facts=matched_facts,
        unmatched_facts=unmatched_facts,
    )


# ---------------------------------------------------------------------------
# Thresholds for binary accuracy (used by McNemar's test)
# ---------------------------------------------------------------------------

ACCURACY_THRESHOLD: float = 0.5
"""
factual_accuracy ≥ this threshold → answer is classed as "correct" for
McNemar's paired binary comparison.  Documented here so it is never silently
changed post-experiment.
"""


def is_correct(result: FactMatchResult) -> bool:
    """Binary correct/incorrect classification for McNemar's test."""
    return result.factual_accuracy >= ACCURACY_THRESHOLD
