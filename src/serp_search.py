"""
SerpAPI module — Google Maps (with Place Details), Google Local, and Yelp.
Pulls structured data directly from search engines via API.
"""

from serpapi import GoogleSearch


# ── Google Maps listing search ──────────────────────────────────────

def search_google_maps(
    query: str,
    api_key: str,
    num_results: int = 60,
    lat: float | None = None,
    lng: float | None = None,
    zoom: int = 12,
) -> list[dict]:
    """
    Search Google Maps for local businesses.
    Returns structured records with name, address, phone, rating, etc.
    """
    all_results = []
    start = 0
    per_page = 20

    while len(all_results) < num_results:
        params = {
            "engine": "google_maps",
            "q": query,
            "type": "search",
            "api_key": api_key,
            "start": start,
            "hl": "en",
        }
        if lat is not None and lng is not None:
            params["ll"] = f"@{lat},{lng},{zoom}z"

        search = GoogleSearch(params)
        data = search.get_dict()
        local_results = data.get("local_results", [])

        if not local_results:
            break

        for item in local_results:
            record = _parse_maps_item(item)
            all_results.append(record)

        start += per_page
        if len(local_results) < per_page:
            break

    return all_results[:num_results]


def _parse_maps_item(item: dict) -> dict:
    """Parse a single Google Maps result into a flat record."""
    record = {
        "Name": item.get("title", ""),
        "Address": item.get("address", ""),
        "Phone": item.get("phone", ""),
        "Website": item.get("website", ""),
        "Rating": item.get("rating", ""),
        "Reviews Count": item.get("reviews", ""),
        "Type / Category": item.get("type", ""),
        "Hours": _flatten_hours(item.get("operating_hours", item.get("hours", ""))),
        "Price Level": item.get("price", ""),
        "Description": item.get("description", ""),
        "Latitude": item.get("gps_coordinates", {}).get("latitude", ""),
        "Longitude": item.get("gps_coordinates", {}).get("longitude", ""),
        "Place ID": item.get("place_id", ""),
        "Data ID": item.get("data_id", ""),
        "Thumbnail": item.get("thumbnail", ""),
        "Data Source": "Google Maps",
    }

    # Extract service options if available
    service_opts = item.get("service_options", {})
    if isinstance(service_opts, dict):
        opts = [k for k, v in service_opts.items() if v]
        if opts:
            record["Service Options"] = ", ".join(opts)

    # Extract extensions (extra tags Google shows)
    extensions = item.get("extensions", [])
    if extensions:
        record["Tags"] = ", ".join(str(e) for e in extensions)

    return record


# ── Google Maps Place Details ───────────────────────────────────────

def get_place_details(data_id: str, api_key: str) -> dict:
    """
    Get detailed info for a single place using its data_id.
    Returns rich data: full hours, reviews summary, amenities, etc.
    """
    params = {
        "engine": "google_maps",
        "type": "place",
        "data_id": data_id,
        "api_key": api_key,
        "hl": "en",
    }
    search = GoogleSearch(params)
    data = search.get_dict()

    place = data.get("place_results", data)
    info = {}

    info["Name"] = place.get("title", "")
    info["Address"] = place.get("address", "")
    info["Phone"] = place.get("phone", "")
    info["Website"] = place.get("website", "")
    info["Rating"] = place.get("rating", "")
    info["Reviews Count"] = place.get("reviews", "")
    info["Type / Category"] = place.get("type", "")
    info["Description"] = place.get("description", "")
    info["Price Level"] = place.get("price", "")
    info["Hours"] = _flatten_hours(place.get("operating_hours", place.get("hours", "")))

    # Rich fields from detail page
    info["Full Address"] = place.get("address", "")
    info["Plus Code"] = place.get("plus_code", "")

    # User reviews summary
    reviews_data = place.get("user_reviews", place.get("reviews_results", {}))
    if isinstance(reviews_data, dict):
        most_relevant = reviews_data.get("most_relevant", [])
        if most_relevant:
            snippets = [r.get("snippet", r.get("text", ""))[:150] for r in most_relevant[:3] if r.get("snippet") or r.get("text")]
            info["Top Reviews"] = " | ".join(snippets)

    # Amenities / service options
    amenities = place.get("amenities", [])
    if amenities:
        if isinstance(amenities, list):
            info["Amenities"] = ", ".join(str(a) for a in amenities)
        elif isinstance(amenities, dict):
            info["Amenities"] = ", ".join(f"{k}: {v}" for k, v in amenities.items())

    service_options = place.get("service_options", {})
    if isinstance(service_options, dict):
        opts = [k for k, v in service_options.items() if v]
        info["Service Options"] = ", ".join(opts)

    extensions = place.get("extensions", [])
    if extensions:
        info["Tags"] = ", ".join(str(e) for e in extensions)

    # Popular times
    popular = place.get("popular_times", {})
    if popular and isinstance(popular, dict):
        busiest = []
        for day, hours_data in popular.items():
            if isinstance(hours_data, list):
                peak = max(hours_data, key=lambda h: h.get("percentage", 0) if isinstance(h, dict) else 0, default={})
                if isinstance(peak, dict) and peak.get("percentage", 0) > 50:
                    busiest.append(f"{day} {peak.get('time', '')}")
        if busiest:
            info["Busiest Times"] = "; ".join(busiest[:5])

    return {k: v for k, v in info.items() if v}


def enrich_with_place_details(
    records: list[dict],
    api_key: str,
    max_places: int = 20,
    progress_callback=None,
) -> list[dict]:
    """
    For each record that has a data_id, fetch full place details
    and merge the extra fields back in.
    """
    enriched = []
    fetched = 0

    for i, record in enumerate(records):
        data_id = record.get("Data ID", "")
        if data_id and fetched < max_places:
            if progress_callback:
                progress_callback(fetched, max_places, record.get("Name", ""))
            try:
                details = get_place_details(data_id, api_key)
                # Merge: details fill in gaps, don't overwrite existing values
                merged = {**record}
                for k, v in details.items():
                    if k not in merged or not merged[k]:
                        merged[k] = v
                enriched.append(merged)
                fetched += 1
            except Exception as e:
                enriched.append(record)
        else:
            enriched.append(record)

    return enriched


# ── Google Local (regular Google search with local pack) ────────────

def search_google_local(
    query: str, api_key: str, location: str = "", num_results: int = 40
) -> list[dict]:
    """Search regular Google for local business results (local pack)."""
    results = []

    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "num": min(num_results, 100),
        "hl": "en",
    }
    if location:
        params["location"] = location

    search = GoogleSearch(params)
    data = search.get_dict()

    for item in data.get("local_results", {}).get("places", []):
        results.append({
            "Name": item.get("title", ""),
            "Address": item.get("address", ""),
            "Phone": item.get("phone", ""),
            "Website": item.get("website", ""),
            "Rating": item.get("rating", ""),
            "Reviews Count": item.get("reviews", ""),
            "Type / Category": item.get("type", ""),
            "Hours": item.get("hours", ""),
            "Data Source": "Google Local Pack",
        })

    return results


# ── Yelp search ─────────────────────────────────────────────────────

def search_yelp(query: str, api_key: str, location: str = "", num_results: int = 30) -> list[dict]:
    """Search Yelp via SerpAPI for additional business data."""
    results = []

    params = {
        "engine": "yelp",
        "find_desc": query,
        "api_key": api_key,
    }
    if location:
        params["find_loc"] = location

    try:
        search = GoogleSearch(params)
        data = search.get_dict()

        for item in data.get("organic_results", []):
            results.append({
                "Name": item.get("title", ""),
                "Address": item.get("neighborhood", item.get("address", "")),
                "Phone": item.get("phone", ""),
                "Website": item.get("link", ""),
                "Rating": item.get("rating", ""),
                "Reviews Count": item.get("reviews", ""),
                "Type / Category": item.get("categories", ""),
                "Price Level": item.get("price_range", ""),
                "Yelp Snippet": item.get("snippet", ""),
                "Data Source": "Yelp",
            })
    except Exception as e:
        print(f"[SerpAPI/Yelp] Error: {e}")

    return results[:num_results]


# ── Multi-query search with dedup ───────────────────────────────────

def search_serp_multiple(
    queries: list[str],
    api_key: str,
    results_per_query: int = 40,
    lat: float | None = None,
    lng: float | None = None,
) -> list[dict]:
    """Run multiple Google Maps searches and deduplicate."""
    all_results = []
    seen_names = set()

    for query in queries:
        try:
            results = search_google_maps(
                query, api_key, num_results=results_per_query, lat=lat, lng=lng
            )
            for r in results:
                name_key = r.get("Name", "").strip().lower()
                if name_key and name_key not in seen_names:
                    seen_names.add(name_key)
                    all_results.append(r)
        except Exception as e:
            print(f"[SerpAPI] Error searching '{query}': {e}")

    return all_results


# ── Helpers ─────────────────────────────────────────────────────────

def _flatten_hours(hours) -> str:
    """Convert hours from dict/list to readable string."""
    if isinstance(hours, dict):
        return "; ".join(f"{day}: {time_str}" for day, time_str in hours.items())
    if isinstance(hours, list):
        return "; ".join(str(h) for h in hours)
    return str(hours) if hours else ""
