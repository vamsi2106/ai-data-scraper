"""
AI Agent module — RCAFT-enhanced query generation, smart keyword strategy,
deterministic fuzzy merge.
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


# ── Smart query generation using RCAFT-enhanced context ─────────────

def generate_maps_queries(
    api_key: str, enhanced_prompt: str, search_keywords: list[str], location: str, num_queries: int = 4
) -> list[str]:
    """Generate Google Maps search queries using RCAFT-enhanced context."""
    system = (
        "You generate Google Maps search queries for maximum business coverage.\n"
        "Return ONLY a JSON array of query strings.\n\n"
        "Strategy:\n"
        "- Include broad category queries ('spas in Hyderabad')\n"
        "- Include specific niche queries ('ayurvedic spa Banjara Hills Hyderabad')\n"
        "- Include service-based queries ('body massage wellness center Hyderabad')\n"
        "- Include area-specific queries for different neighborhoods\n"
        "- Use the provided keywords as inspiration but optimize for Google Maps"
    )
    keywords_str = ", ".join(search_keywords[:10]) if search_keywords else ""
    user = (
        f"Enhanced requirement: {enhanced_prompt}\n"
        f"Location: {location}\n"
        f"Seed keywords: {keywords_str}\n\n"
        f"Generate exactly {num_queries} diverse Google Maps queries for maximum coverage."
    )
    client = _client(api_key)
    raw = _chat(client, system, user)
    queries = _extract_json(raw)
    if isinstance(queries, list):
        return [str(q) for q in queries[:num_queries]]
    raise ValueError("AI did not return a list of queries")


def generate_web_search_queries(
    api_key: str, enhanced_prompt: str, search_keywords: list[str], location: str, target_sources: list[str], num_queries: int = 5
) -> list[str]:
    """
    Generate Google web search queries targeting DIRECTORY SITES, REVIEW SITES,
    and THIRD-PARTY sources that have data NOT available on official business websites.
    """
    system = (
        "You generate Google web search queries specifically designed to find\n"
        "business data on THIRD-PARTY sites — NOT the businesses' own websites.\n\n"
        "Return ONLY a JSON array of query strings.\n\n"
        "Target these source types:\n"
        "- Indian business directories: JustDial, Sulekha, IndiaMART, TradeIndia\n"
        "- Review platforms: TripAdvisor, Google Reviews, MouthShut, Yelp\n"
        "- Listing aggregators: Practo, UrbanClap, BookMyShow, NearBuy\n"
        "- Blog/article listings: 'top 10 spas in [city]', 'best rated [business]'\n"
        "- Yellow pages and B2B directories\n"
        "- Government/licensing databases if applicable\n\n"
        "Use 'site:' operator for known directories.\n"
        "Use 'intitle:' for article/list-style pages.\n"
        "Use location qualifiers for geographic targeting.\n"
        "These queries will be used with regular Google search, NOT Google Maps."
    )
    sources_str = ", ".join(target_sources[:10]) if target_sources else ""
    keywords_str = ", ".join(search_keywords[:10]) if search_keywords else ""
    user = (
        f"Requirement: {enhanced_prompt}\n"
        f"Location: {location}\n"
        f"Target sources: {sources_str}\n"
        f"Keywords: {keywords_str}\n\n"
        f"Generate exactly {num_queries} Google web search queries that will find:\n"
        "1. Directory listings with detailed business profiles\n"
        "2. Review pages with ratings, comments, and details\n"
        "3. Blog/article pages that list and compare businesses\n"
        "4. Third-party sites with data like pricing, amenities, staff info\n"
        "5. Any source with information NOT on the business's own website"
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
    for key in ["Name", "name", "Business Name", "business_name", "Title", "title"]:
        val = record.get(key, "")
        if val:
            return str(val).strip()
    return ""


def _normalize_name(name: str) -> str:
    """Normalize a business name for matching. Domain-agnostic."""
    import re as _re
    name = name.lower().strip()
    # Remove common location/city suffixes (generic pattern)
    name = _re.sub(r'\s*[-–,]\s*\w+$', '', name)
    # Remove extra whitespace
    name = _re.sub(r'\s+', ' ', name)
    return name.strip()


def fuzzy_merge_records(
    primary: list[dict],
    *secondary_lists: list[dict],
    match_threshold: int = 70,
) -> list[dict]:
    """
    Merge multiple record lists using fuzzy name matching.
    Primary records are the base. Secondary fills gaps or appends new ones.
    No data lost. No LLM. Deterministic.
    """
    merged = [dict(r) for r in primary]
    merged_names = [_normalize_name(_get_name(r)) for r in merged]

    for secondary in secondary_lists:
        for sec_record in secondary:
            sec_name = _normalize_name(_get_name(sec_record))
            if not sec_name:
                merged.append(dict(sec_record))
                merged_names.append("")
                continue

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
                for k, v in sec_record.items():
                    if v is not None and str(v).strip():
                        existing = merged[best_idx].get(k)
                        if not existing or not str(existing).strip():
                            merged[best_idx][k] = v
            else:
                merged.append(dict(sec_record))
                merged_names.append(sec_name)

    return merged


def deduplicate_by_name(records: list[dict], threshold: int = 85) -> list[dict]:
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
