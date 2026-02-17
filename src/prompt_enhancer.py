"""
RCAFT Prompt Enhancer — transforms raw user input into a rich, structured prompt
using the RCAFT framework (Role, Context, Action, Format, Tone).

Fully dynamic: works for ANY business type or search scenario.
The AI decides what fields and research categories are relevant.
"""

import json
import re
from openai import OpenAI

from src.config import OPENAI_MODEL


def _client(api_key: str) -> OpenAI:
    return OpenAI(api_key=api_key)


def enhance_prompt(api_key: str, raw_input: str) -> dict:
    """
    Enhance raw user input using RCAFT. Returns everything needed
    to drive a fully dynamic pipeline — no hardcoded fields.

    Returns:
        {
            "enhanced_prompt": str,
            "rcaft": { role, context, action, format, tone },
            "search_keywords": [str],
            "data_fields": [str],
            "field_groups": [
                { "group_name": str, "fields": [str], "research_prompt": str }
            ],
            "target_sources": [str],
            "location": str,
            "domain": str,
        }
    """
    client = _client(api_key)

    system = (
        "You are a Prompt Engineering Expert specializing in the RCAFT framework.\n\n"
        "RCAFT stands for:\n"
        "  R — Role: Define who the AI should act as\n"
        "  C — Context: Background, domain, geographic, industry context\n"
        "  A — Action: Specific actions to perform\n"
        "  F — Format: Data structure and fields\n"
        "  T — Tone: Communication style\n\n"
        "You must analyze the user's intent and produce a FULLY DYNAMIC output.\n"
        "The user could be searching for ANY type of business or data — restaurants, "
        "hospitals, hotels, IT companies, gyms, car dealers, lawyers, factories, etc.\n\n"
        "Return ONLY a valid JSON object with these keys:\n"
        "  enhanced_prompt, rcaft, search_keywords, data_fields, field_groups, "
        "target_sources, location, domain\n\n"
        "CRITICAL — field_groups:\n"
        "  This is the most important part. Break the data collection into 3-5 research\n"
        "  groups, each targeting a DIFFERENT CATEGORY of information.\n"
        "  Each group has:\n"
        "    - group_name: short label (e.g., 'Services & Offerings', 'Pricing & Packages')\n"
        "    - fields: list of specific field names to extract for this group\n"
        "    - research_prompt: a detailed prompt that tells Perplexity AI exactly what\n"
        "      to research for each business in this group. Be SPECIFIC about what data\n"
        "      to find and where to look. Include example values so the AI knows the\n"
        "      level of detail expected.\n\n"
        "  The groups must be RELEVANT to the user's domain. Examples:\n"
        "  - For restaurants: Menu & Cuisine, Pricing, Ambience & Seating, Delivery Options\n"
        "  - For hospitals: Departments & Specialties, Doctors, Insurance, Bed Capacity\n"
        "  - For IT companies: Services, Tech Stack, Client Portfolio, Team Size\n"
        "  - For gyms: Equipment & Facilities, Membership Plans, Trainers, Class Schedule\n"
        "  DO NOT use generic spa-specific groups unless the user actually asks about spas."
    )

    user = (
        f"Raw user input:\n\"{raw_input}\"\n\n"
        "Apply RCAFT and produce the full dynamic output.\n\n"
        "For search_keywords: 8-12 diverse keywords targeting:\n"
        "- Business directories (JustDial, Sulekha, Yellow Pages, industry-specific)\n"
        "- Review sites (Google, TripAdvisor, Yelp, MouthShut, domain-specific)\n"
        "- Third-party data aggregators\n"
        "- Blog posts and comparison articles\n\n"
        "For data_fields: every specific piece of information worth collecting\n"
        "for THIS particular domain/business type.\n\n"
        "For field_groups: 3-5 research categories with detailed prompts.\n"
        "Each research_prompt should be 2-4 sentences telling Perplexity EXACTLY\n"
        "what to search for, what level of detail to provide, and example values.\n\n"
        "For target_sources: specific websites and source types relevant to this domain.\n\n"
        "IMPORTANT: Everything must be specific to what the user is actually searching for."
    )

    resp = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.3,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )

    raw_response = resp.choices[0].message.content.strip()
    result = _extract_json(raw_response)

    if not isinstance(result, dict) or "enhanced_prompt" not in result:
        return _fallback(raw_input)

    # Ensure field_groups exist
    if "field_groups" not in result or not result["field_groups"]:
        result["field_groups"] = _generate_default_field_groups(raw_input)

    return result


def _fallback(raw_input: str) -> dict:
    """Fallback if enhancement fails."""
    return {
        "enhanced_prompt": raw_input,
        "rcaft": {
            "role": "Data Research Expert",
            "context": raw_input,
            "action": "Find and compile comprehensive business data",
            "format": "Structured records with all available fields",
            "tone": "Professional, thorough, data-driven",
        },
        "search_keywords": [raw_input],
        "data_fields": ["Name", "Address", "Phone", "Website", "Rating", "Description"],
        "field_groups": _generate_default_field_groups(raw_input),
        "target_sources": ["Google Maps", "Business directories", "Review sites"],
        "location": "",
        "domain": "",
    }


def _generate_default_field_groups(raw_input: str) -> list[dict]:
    """Generic field groups when AI doesn't produce them."""
    return [
        {
            "group_name": "Services & Offerings",
            "fields": ["Services", "Specialties", "Products", "Key Offerings"],
            "research_prompt": (
                f"For each business, find their complete list of services, products, "
                f"specialties, and key offerings. Context: {raw_input}"
            ),
        },
        {
            "group_name": "Pricing & Packages",
            "fields": ["Price Range", "Packages", "Pricing Details", "Payment Methods"],
            "research_prompt": (
                f"For each business, find pricing information including price ranges, "
                f"packages, membership plans, and accepted payment methods. Context: {raw_input}"
            ),
        },
        {
            "group_name": "Operations & Capacity",
            "fields": ["Operating Hours", "Capacity", "Staff Count", "Year Established"],
            "research_prompt": (
                f"For each business, find operational details: hours of operation, "
                f"capacity, team size, and when they were established. Context: {raw_input}"
            ),
        },
    ]


def _extract_json(text: str):
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for sc, ec in [("{", "}"), ("[", "]")]:
        s = text.find(sc)
        e = text.rfind(ec)
        if s != -1 and e != -1 and e > s:
            try:
                return json.loads(text[s : e + 1])
            except json.JSONDecodeError:
                continue
    return None
