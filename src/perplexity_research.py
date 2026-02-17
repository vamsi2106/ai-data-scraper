"""
Perplexity AI module — fully dynamic research using sonar-pro.
No hardcoded fields. Research prompts come from RCAFT field_groups.
"""

import json
import re
from openai import OpenAI


def _client(api_key: str) -> OpenAI:
    return OpenAI(api_key=api_key, base_url="https://api.perplexity.ai")


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
    return None


def _call_perplexity(client: OpenAI, system: str, user: str, model: str = "sonar-pro") -> str:
    resp = client.chat.completions.create(
        model=model,
        temperature=0.1,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content.strip()


# ── 1. Discover businesses (dynamic) ────────────────────────────────

def research_businesses(
    api_key: str,
    requirement: str,
    data_fields: list[str] | None = None,
    existing_names: list[str] | None = None,
) -> list[dict]:
    """
    Discover businesses matching the requirement.
    Uses data_fields from RCAFT to know what basic info to return.
    """
    client = _client(api_key)

    skip_context = ""
    if existing_names:
        skip_context = (
            "\n\nI already have these — find ADDITIONAL ones not in this list:\n"
            + ", ".join(existing_names[:50])
        )

    # Use RCAFT data_fields if available, otherwise basic fields
    if data_fields:
        basic_fields = [f for f in data_fields if f.lower() in (
            "name", "address", "phone", "website", "rating", "email",
            "description", "type", "category",
        )]
        if len(basic_fields) < 3:
            basic_fields = ["Name", "Address", "Phone", "Website", "Rating"]
    else:
        basic_fields = ["Name", "Address", "Phone", "Website", "Rating"]

    fields_str = ", ".join(basic_fields)

    system = (
        "You are a data researcher with real-time web search capabilities.\n"
        "Find and list ALL businesses/entities matching the requirement.\n"
        "Return ONLY a valid JSON array of objects.\n"
        f"Each object must have these fields: {fields_str}\n"
        "Use null for unknown fields. Do NOT hallucinate. Only use real data from the web.\n"
        "Find as many as possible — aim for 20-30+ results.\n"
        "Include businesses from ALL sources: directories, review sites, articles, etc."
    )
    user = (
        f"Find ALL matching entities for: {requirement}\n\n"
        f"Return a JSON array with {fields_str} "
        f"for every match you can find.{skip_context}"
    )

    raw = _call_perplexity(client, system, user)
    records = _extract_json(raw)

    if isinstance(records, list):
        for r in records:
            if isinstance(r, dict):
                r["Data Source"] = "Perplexity AI"
        return [r for r in records if isinstance(r, dict)]
    return []


# ── 2. Dynamic field group research ─────────────────────────────────

def research_field_group(
    api_key: str,
    requirement: str,
    business_names: list[str],
    group_name: str,
    fields: list[str],
    research_prompt: str,
) -> list[dict]:
    """
    Research a specific group of fields for a list of businesses.
    Fully dynamic — the fields and research prompt come from RCAFT.
    """
    client = _client(api_key)
    all_records = []
    fields_str = ", ".join(fields)

    for batch in _batch_names(business_names, batch_size=12):
        names_str = "\n".join(f"  {i+1}. {n}" for i, n in enumerate(batch))

        system = (
            f"You are a data researcher specializing in {group_name}.\n"
            "You have real-time web search access. Look up REAL data for each business.\n"
            "Return ONLY a valid JSON array of objects.\n"
            f"Each object must have: Name, {fields_str}\n"
            "Use null for unknown fields. Do NOT make up data.\n"
            "Search directories, review sites, articles, social media — any public source."
        )
        user = (
            f"Context: {requirement}\n\n"
            f"Research task: {research_prompt}\n\n"
            f"For each business below, find: {fields_str}\n\n"
            f"Businesses:\n{names_str}\n\n"
            f"Return a JSON array with Name + {fields_str} for each business."
        )

        raw = _call_perplexity(client, system, user)
        records = _extract_json(raw)
        if isinstance(records, list):
            all_records.extend([r for r in records if isinstance(r, dict)])

    return all_records


# ── 3. Research all field groups ─────────────────────────────────────

def research_all_field_groups(
    api_key: str,
    requirement: str,
    business_names: list[str],
    field_groups: list[dict],
    progress_callback=None,
) -> dict[str, list[dict]]:
    """
    Research ALL field groups from RCAFT output.
    Returns a dict: { group_name: [records] }
    """
    results = {}

    for i, group in enumerate(field_groups):
        group_name = group.get("group_name", f"Group {i+1}")
        fields = group.get("fields", [])
        research_prompt = group.get("research_prompt", "")

        if not fields:
            continue

        if progress_callback:
            progress_callback(i, len(field_groups), group_name)

        try:
            records = research_field_group(
                api_key, requirement, business_names,
                group_name, fields, research_prompt,
            )
            results[group_name] = records
        except Exception as e:
            print(f"[Perplexity] Error researching '{group_name}': {e}")
            results[group_name] = []

    return results


# ── Helpers ──────────────────────────────────────────────────────────

def _batch_names(names: list[str], batch_size: int = 12):
    for i in range(0, len(names), batch_size):
        yield names[i : i + batch_size]
