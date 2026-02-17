"""
Perplexity AI module — uses sonar-pro for deep, search-grounded research.
Multiple focused calls instead of one broad one. Batched enrichment without caps.
"""

import json
import re
from openai import OpenAI


def _client(api_key: str) -> OpenAI:
    return OpenAI(api_key=api_key, base_url="https://api.perplexity.ai")


def _extract_json(text: str):
    """Best-effort JSON extraction from LLM output."""
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
    return None


def _call_perplexity(client: OpenAI, system: str, user: str, model: str = "sonar-pro") -> str:
    """Single Perplexity API call."""
    resp = client.chat.completions.create(
        model=model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content.strip()


# ── 1. Discover businesses (broad search) ───────────────────────────

def research_businesses(api_key: str, requirement: str, existing_names: list[str] | None = None) -> list[dict]:
    """
    Use Perplexity sonar-pro to find and list businesses with basic info.
    Focused call: just names, addresses, phones, websites.
    """
    client = _client(api_key)

    skip_context = ""
    if existing_names:
        skip_context = (
            "\n\nI already have these businesses — find ADDITIONAL ones not in this list:\n"
            + ", ".join(existing_names[:50])
        )

    system = (
        "You are a business data researcher with web search capabilities.\n"
        "Find and list ALL businesses matching the requirement.\n"
        "Return ONLY a valid JSON array of objects.\n"
        "Each object must have: Name, Address, Phone, Website, Rating.\n"
        "Use null for unknown fields. Do NOT hallucinate. Only use real data from the web.\n"
        "Find as many as possible — aim for 20-30+ results."
    )
    user = (
        f"Find ALL businesses for: {requirement}\n\n"
        "Return a JSON array with Name, Address, Phone, Website, Rating "
        f"for every business you can find.{skip_context}"
    )

    raw = _call_perplexity(client, system, user)
    records = _extract_json(raw)

    if isinstance(records, list):
        for r in records:
            if isinstance(r, dict):
                r["Data Source"] = "Perplexity AI"
        return [r for r in records if isinstance(r, dict)]
    return []


# ── 2. Research specific aspects (focused calls) ────────────────────

def research_amenities_and_services(api_key: str, requirement: str, business_names: list[str]) -> list[dict]:
    """Focused call: look up amenities, services, and facilities for each business."""
    client = _client(api_key)
    all_records = []

    for batch in _batch_names(business_names, batch_size=15):
        names_str = "\n".join(f"  {i+1}. {n}" for i, n in enumerate(batch))
        system = (
            "You are a business data researcher. Look up REAL amenities, services, "
            "and facilities for each listed business from the web.\n"
            "Return ONLY a valid JSON array. Use null for unknown fields. Do NOT make up data."
        )
        user = (
            f"Context: {requirement}\n\n"
            f"For each business below, find their:\n"
            "- Amenities (e.g., steam room, sauna, jacuzzi, pool, parking, wifi)\n"
            "- Services offered (e.g., Swedish massage, Thai massage, facial, body scrub)\n"
            "- Facilities (e.g., couple rooms, private rooms, locker rooms)\n\n"
            f"Businesses:\n{names_str}\n\n"
            "Return JSON array with: Name, Amenities, Services, Facilities for each."
        )
        raw = _call_perplexity(client, system, user)
        records = _extract_json(raw)
        if isinstance(records, list):
            all_records.extend([r for r in records if isinstance(r, dict)])

    return all_records


def research_capacity_and_staff(api_key: str, requirement: str, business_names: list[str]) -> list[dict]:
    """Focused call: look up room capacity, staff count, size details."""
    client = _client(api_key)
    all_records = []

    for batch in _batch_names(business_names, batch_size=15):
        names_str = "\n".join(f"  {i+1}. {n}" for i, n in enumerate(batch))
        system = (
            "You are a business data researcher. Look up capacity and staffing "
            "information for each listed business from the web.\n"
            "Return ONLY a valid JSON array. Use null for unknown fields. Do NOT make up data."
        )
        user = (
            f"Context: {requirement}\n\n"
            f"For each business below, find:\n"
            "- Room Capacity (number of treatment rooms, total capacity)\n"
            "- Staff Count (number of therapists, total employees)\n"
            "- Size / Area (square footage if available)\n"
            "- Year Established\n\n"
            f"Businesses:\n{names_str}\n\n"
            "Return JSON array with: Name, Room Capacity, Staff Count, Area Size, Year Established."
        )
        raw = _call_perplexity(client, system, user)
        records = _extract_json(raw)
        if isinstance(records, list):
            all_records.extend([r for r in records if isinstance(r, dict)])

    return all_records


def research_pricing_and_hours(api_key: str, requirement: str, business_names: list[str]) -> list[dict]:
    """Focused call: look up pricing, packages, and operating hours."""
    client = _client(api_key)
    all_records = []

    for batch in _batch_names(business_names, batch_size=15):
        names_str = "\n".join(f"  {i+1}. {n}" for i, n in enumerate(batch))
        system = (
            "You are a business data researcher. Look up pricing and operating details "
            "for each listed business from the web.\n"
            "Return ONLY a valid JSON array. Use null for unknown fields. Do NOT make up data."
        )
        user = (
            f"Context: {requirement}\n\n"
            f"For each business below, find:\n"
            "- Price Range (e.g., ₹500-₹3000)\n"
            "- Popular Packages (names and prices of top packages)\n"
            "- Operating Hours (opening and closing times)\n"
            "- Payment Methods accepted\n\n"
            f"Businesses:\n{names_str}\n\n"
            "Return JSON array with: Name, Price Range, Popular Packages, Operating Hours, Payment Methods."
        )
        raw = _call_perplexity(client, system, user)
        records = _extract_json(raw)
        if isinstance(records, list):
            all_records.extend([r for r in records if isinstance(r, dict)])

    return all_records


# ── 3. All-in-one enrichment (single broad call per batch) ──────────

def enrich_all_fields(
    api_key: str, requirement: str, business_names: list[str], fields: list[str]
) -> list[dict]:
    """
    Enrich businesses with specified fields. Batches automatically — no cap.
    """
    client = _client(api_key)
    all_records = []
    fields_str = ", ".join(fields)

    for batch in _batch_names(business_names, batch_size=12):
        names_str = "\n".join(f"  {i+1}. {n}" for i, n in enumerate(batch))
        system = (
            "You are a business data researcher with web search. "
            "Look up specific details for each business.\n"
            "Return ONLY a valid JSON array. Use null for unknown fields. Do NOT make up data."
        )
        user = (
            f"Context: {requirement}\n\n"
            f"For each business, find these fields: {fields_str}\n\n"
            f"Businesses:\n{names_str}\n\n"
            "Return a JSON array with Name + all the requested fields for each business."
        )
        raw = _call_perplexity(client, system, user)
        records = _extract_json(raw)
        if isinstance(records, list):
            all_records.extend([r for r in records if isinstance(r, dict)])

    return all_records


# ── Helpers ─────────────────────────────────────────────────────────

def _batch_names(names: list[str], batch_size: int = 15):
    """Yield successive batches of names."""
    for i in range(0, len(names), batch_size):
        yield names[i : i + batch_size]
