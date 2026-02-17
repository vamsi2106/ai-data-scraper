"""
AI Agent module — query generation + deterministic fuzzy merge (no LLM merge).
"""

import json
import re
from openai import OpenAI
from thefuzz import fuzz

from src.config import OPENAI_MODEL


def _client(api_key: str) -> OpenAI:
    return OpenAI(api_key=api_key)


def _chat(client: OpenAI, system: str, user: str, model: str = OPENAI_MODEL, temperature: float = 0.2) -> str:
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content.strip()


def _extract_json(text: str):
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for sc, ec in [("[", "]"), ("{", "}")]:
        s = text.find(sc)
        e = text.rfind(ec)
        if s != -1 and e != -1 and e > s:
            try:
                return json.loads(text[s : e + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"Could not extract JSON:\n{text[:500]}")


# ── Query generation ────────────────────────────────────────────────

def generate_search_queries(api_key: str, requirement: str, num_queries: int = 3) -> list[str]:
    """Generate optimized Google Maps search queries."""
    system = (
        "You generate Google Maps search queries for finding local businesses.\n"
        "Return ONLY a JSON array of search query strings.\n"
        "Each query should target a different angle to maximize coverage:\n"
        "- One broad query (e.g., 'spas in Hyderabad')\n"
        "- One specific query (e.g., 'luxury wellness spa Hyderabad Banjara Hills')\n"
        "- One niche query (e.g., 'ayurvedic spa treatment center Hyderabad')"
    )
    user = (
        f"Requirement: {requirement}\n\n"
        f"Generate exactly {num_queries} diverse Google Maps search queries."
    )
    client = _client(api_key)
    raw = _chat(client, system, user)
    queries = _extract_json(raw)
    if isinstance(queries, list):
        return [str(q) for q in queries[:num_queries]]
    raise ValueError("AI did not return a list of queries")


def generate_location_info(api_key: str, requirement: str) -> dict:
    """Extract location coordinates and name from the requirement."""
    system = (
        "Given a data-collection requirement, extract the geographic location.\n"
        "Return a JSON object with: city, country, latitude, longitude, yelp_location\n"
        "The lat/lng should be the city center coordinates.\n"
        "yelp_location should be the city name suitable for Yelp search."
    )
    user = f"Requirement: {requirement}"
    client = _client(api_key)
    raw = _chat(client, system, user)
    try:
        return _extract_json(raw)
    except (ValueError, json.JSONDecodeError):
        return {}


# ── Deterministic fuzzy merge (no LLM) ─────────────────────────────

def _get_name(record: dict) -> str:
    """Extract the name from a record, trying common key variations."""
    for key in ["Name", "name", "Business Name", "business_name", "Title", "title"]:
        val = record.get(key, "")
        if val:
            return str(val).strip()
    return ""


def _normalize_name(name: str) -> str:
    """Normalize a business name for matching."""
    name = name.lower().strip()
    # Remove common suffixes
    for suffix in [" - hyderabad", " hyderabad", ", hyderabad", " spa", " wellness"]:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name.strip()


def fuzzy_merge_records(
    primary: list[dict],
    *secondary_lists: list[dict],
    match_threshold: int = 70,
) -> list[dict]:
    """
    Merge multiple record lists using fuzzy name matching.
    - primary records are the base (never dropped)
    - secondary records enrich primary or get appended if no match
    - No data is lost. No LLM involved. Deterministic.
    """
    # Build the merged list starting from primary
    merged = [dict(r) for r in primary]  # deep copy
    merged_names = [_normalize_name(_get_name(r)) for r in merged]

    for secondary in secondary_lists:
        for sec_record in secondary:
            sec_name = _normalize_name(_get_name(sec_record))
            if not sec_name:
                merged.append(dict(sec_record))
                merged_names.append("")
                continue

            # Find best match in merged
            best_score = 0
            best_idx = -1
            for i, m_name in enumerate(merged_names):
                if not m_name:
                    continue
                score = fuzz.token_sort_ratio(sec_name, m_name)
                if score > best_score:
                    best_score = score
                    best_idx = i

            if best_score >= match_threshold and best_idx >= 0:
                # Merge: fill in gaps in the primary record
                for k, v in sec_record.items():
                    if v is not None and str(v).strip():
                        existing = merged[best_idx].get(k)
                        if not existing or not str(existing).strip():
                            merged[best_idx][k] = v
            else:
                # No match — new business, append it
                merged.append(dict(sec_record))
                merged_names.append(sec_name)

    return merged


def deduplicate_by_name(records: list[dict], threshold: int = 85) -> list[dict]:
    """Remove near-duplicate records by fuzzy name matching."""
    result = []
    seen_names = []

    for record in records:
        name = _normalize_name(_get_name(record))
        if not name:
            result.append(record)
            continue

        is_dup = False
        for existing_name in seen_names:
            if fuzz.token_sort_ratio(name, existing_name) >= threshold:
                is_dup = True
                break

        if not is_dup:
            result.append(record)
            seen_names.append(name)

    return result
