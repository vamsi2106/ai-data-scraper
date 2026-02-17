"""
AI-Powered Data Scraper (v2)
============================
SerpAPI (Maps + Place Details + Yelp) + Perplexity AI (sonar-pro, focused calls)
+ Fuzzy merge in code. Maximum data, straight to Excel.
"""

import time
import streamlit as st
import pandas as pd

from src.ai_agent import (
    generate_search_queries,
    generate_location_info,
    fuzzy_merge_records,
    deduplicate_by_name,
)
from src.serp_search import (
    search_serp_multiple,
    enrich_with_place_details,
    search_google_local,
    search_yelp,
)
from src.perplexity_research import (
    research_businesses,
    research_amenities_and_services,
    research_capacity_and_staff,
    research_pricing_and_hours,
)
from src.excel_exporter import export_to_excel
from src.config import OPENAI_API_KEY, SERPAPI_KEY, PERPLEXITY_API_KEY

# ─── Page Config ──────────────────────────────────────────────────────
st.set_page_config(page_title="AI Data Scraper", page_icon="🔍", layout="wide")

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 2rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        text-align: center;
    }
    .main-header h1 { color: #fff; font-size: 2rem; margin: 0 0 0.3rem 0; }
    .main-header p { color: #a0aec0; margin: 0; font-size: 0.95rem; }
</style>
""", unsafe_allow_html=True)

# ─── Sidebar ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔑 API Keys")
    if OPENAI_API_KEY and SERPAPI_KEY:
        st.success("Keys loaded from .env file")
    else:
        st.info("Add keys below or set them in `.env` to persist")
    st.markdown("---")

    openai_key = st.text_input("OpenAI API Key", value=OPENAI_API_KEY, type="password", placeholder="sk-...",
                                help="Loaded from .env if set")
    serpapi_key = st.text_input("SerpAPI Key", value=SERPAPI_KEY, type="password", placeholder="your serpapi key",
                                 help="Get free: https://serpapi.com (100 searches/mo)")
    perplexity_key = st.text_input("Perplexity API Key", value=PERPLEXITY_API_KEY, type="password", placeholder="pplx-...",
                                    help="Get at: https://docs.perplexity.ai")

    st.markdown("---")
    st.markdown("## ⚙️ Settings")

    num_queries = st.slider("Google Maps search queries", 1, 6, 3)
    results_per_query = st.slider("Results per Maps query", 10, 80, 40)

    st.markdown("#### SerpAPI Options")
    fetch_place_details = st.checkbox("Fetch Place Details (richer data per business)", value=True,
                                       help="Uses 1 SerpAPI credit per place. Gets amenities, reviews, hours, etc.")
    max_place_details = st.slider("Max places to get details for", 5, 60, 20) if fetch_place_details else 0
    search_yelp_too = st.checkbox("Also search Yelp", value=False,
                                   help="Uses 1 extra SerpAPI credit. Gets Yelp ratings and snippets.")
    search_google_local_too = st.checkbox("Also search Google Local Pack", value=False,
                                           help="Uses 1 extra SerpAPI credit per query.")

    st.markdown("#### Perplexity Options")
    use_perplexity = st.checkbox("Use Perplexity AI", value=True)
    pplx_discover = st.checkbox("Discover additional businesses", value=True,
                                 help="Find businesses not in Google Maps")
    pplx_amenities = st.checkbox("Research amenities & services", value=True)
    pplx_capacity = st.checkbox("Research capacity & staffing", value=True)
    pplx_pricing = st.checkbox("Research pricing & hours", value=True)

    st.markdown("---")
    st.markdown("### Pipeline")
    st.markdown("""
    1. AI generates search queries + location
    2. **SerpAPI** → Google Maps listings
    3. **SerpAPI** → Place Details (per business)
    4. **SerpAPI** → Yelp + Google Local *(optional)*
    5. **Perplexity** → Discover extra businesses
    6. **Perplexity** → Amenities, Capacity, Pricing
    7. **Fuzzy merge** all sources in code (lossless)
    8. Push to Excel
    """)

# ─── Main ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🔍 AI Data Scraper v2</h1>
    <p>SerpAPI (Maps + Place Details + Yelp) + Perplexity sonar-pro — maximum data coverage</p>
</div>
""", unsafe_allow_html=True)

requirement = st.text_area(
    "📝 What data do you need?",
    placeholder="e.g., All spas in Hyderabad with amenities, room capacity, manpower, pricing, contact info...",
    height=100,
)

col1, col2 = st.columns([1, 4])
with col1:
    start_btn = st.button("🚀 Get Data", type="primary", use_container_width=True)
st.markdown("---")

# ─── Pipeline ─────────────────────────────────────────────────────────
if start_btn:
    if not openai_key:
        st.error("Enter your OpenAI API key.")
        st.stop()
    if not serpapi_key:
        st.error("Enter your SerpAPI key.")
        st.stop()
    if use_perplexity and not perplexity_key:
        st.error("Enter your Perplexity API key (or uncheck 'Use Perplexity AI').")
        st.stop()
    if not requirement.strip():
        st.error("Describe what data you need.")
        st.stop()

    t_start = time.time()
    serp_records = []
    yelp_records = []
    local_records = []
    pplx_base_records = []
    pplx_amenity_records = []
    pplx_capacity_records = []
    pplx_pricing_records = []

    # ── Step 1: AI generates queries + location ──
    with st.status("🧠 Step 1: AI generating search queries...", expanded=True) as status:
        try:
            queries = generate_search_queries(openai_key, requirement, num_queries=num_queries)
            for i, q in enumerate(queries, 1):
                st.write(f"  {i}. `{q}`")

            st.write("Detecting location coordinates...")
            loc = generate_location_info(openai_key, requirement)
            lat = loc.get("latitude")
            lng = loc.get("longitude")
            city = loc.get("city", "")
            yelp_loc = loc.get("yelp_location", city)
            if lat and lng:
                st.write(f"  Location: **{city}** ({lat}, {lng})")
            else:
                st.write(f"  Location: **{city}** (no coordinates, using default)")

            status.update(label=f"✅ {len(queries)} queries + location", state="complete")
        except Exception as e:
            st.error(f"Failed: {e}")
            st.stop()

    # ── Step 2: SerpAPI Google Maps ──
    with st.status("🗺️ Step 2: Google Maps listings (SerpAPI)...", expanded=True) as status:
        try:
            serp_records = search_serp_multiple(
                queries, serpapi_key, results_per_query=results_per_query,
                lat=lat, lng=lng,
            )
            st.write(f"**{len(serp_records)} unique businesses from Google Maps**")
            if serp_records:
                names_preview = [r.get("Name", "?") for r in serp_records[:8]]
                st.write("Preview: " + ", ".join(names_preview) + "...")
            status.update(label=f"✅ {len(serp_records)} from Google Maps", state="complete")
        except Exception as e:
            st.warning(f"Google Maps search failed: {e}")

    # ── Step 3: SerpAPI Place Details ──
    if fetch_place_details and serp_records and max_place_details > 0:
        with st.status(f"🏢 Step 3: Fetching Place Details for up to {max_place_details} businesses...", expanded=True) as status:
            progress = st.progress(0)
            detail_log = st.empty()

            def detail_progress(current, total, name):
                progress.progress(current / total if total > 0 else 0)
                detail_log.write(f"  [{current+1}/{total}] {name}")

            try:
                serp_records = enrich_with_place_details(
                    serp_records, serpapi_key, max_places=max_place_details,
                    progress_callback=detail_progress,
                )
                progress.progress(1.0)
                st.write(f"**Enriched {min(max_place_details, len(serp_records))} businesses with full details**")
                status.update(label=f"✅ Place Details enriched", state="complete")
            except Exception as e:
                st.warning(f"Place Details failed: {e}")
    else:
        st.info("Skipping Place Details (disabled or no results).")

    # ── Step 4: Yelp + Google Local (optional) ──
    if search_yelp_too and yelp_loc:
        with st.status("🍽️ Step 4a: Searching Yelp...", expanded=True) as status:
            try:
                yelp_query = queries[0] if queries else requirement
                yelp_records = search_yelp(yelp_query, serpapi_key, location=yelp_loc)
                st.write(f"**{len(yelp_records)} from Yelp**")
                status.update(label=f"✅ {len(yelp_records)} from Yelp", state="complete")
            except Exception as e:
                st.warning(f"Yelp search failed: {e}")

    if search_google_local_too:
        with st.status("📍 Step 4b: Google Local Pack...", expanded=True) as status:
            try:
                for q in queries[:2]:
                    local_records.extend(search_google_local(q, serpapi_key, location=city))
                st.write(f"**{len(local_records)} from Google Local Pack**")
                status.update(label=f"✅ {len(local_records)} from Local Pack", state="complete")
            except Exception as e:
                st.warning(f"Google Local failed: {e}")

    # ── Step 5: Perplexity AI ──
    all_names_so_far = [r.get("Name", "") for r in serp_records + yelp_records + local_records if r.get("Name")]

    if use_perplexity and perplexity_key:
        # 5a: Discover additional businesses
        if pplx_discover:
            with st.status("🔬 Step 5a: Perplexity discovering extra businesses...", expanded=True) as status:
                try:
                    pplx_base_records = research_businesses(perplexity_key, requirement, existing_names=all_names_so_far)
                    st.write(f"**{len(pplx_base_records)} additional businesses from Perplexity**")
                    status.update(label=f"✅ +{len(pplx_base_records)} from Perplexity", state="complete")
                except Exception as e:
                    st.warning(f"Perplexity discovery failed: {e}")

        # Collect all names for enrichment
        all_names_for_enrichment = list(set(
            all_names_so_far + [r.get("Name", "") for r in pplx_base_records if r.get("Name")]
        ))

        # 5b: Amenities & services
        if pplx_amenities and all_names_for_enrichment:
            with st.status(f"🧖 Step 5b: Researching amenities for {len(all_names_for_enrichment)} businesses...", expanded=True) as status:
                try:
                    pplx_amenity_records = research_amenities_and_services(
                        perplexity_key, requirement, all_names_for_enrichment
                    )
                    st.write(f"**Got amenity data for {len(pplx_amenity_records)} businesses**")
                    status.update(label=f"✅ Amenities: {len(pplx_amenity_records)}", state="complete")
                except Exception as e:
                    st.warning(f"Amenity research failed: {e}")

        # 5c: Capacity & staffing
        if pplx_capacity and all_names_for_enrichment:
            with st.status(f"👥 Step 5c: Researching capacity & staff...", expanded=True) as status:
                try:
                    pplx_capacity_records = research_capacity_and_staff(
                        perplexity_key, requirement, all_names_for_enrichment
                    )
                    st.write(f"**Got capacity data for {len(pplx_capacity_records)} businesses**")
                    status.update(label=f"✅ Capacity: {len(pplx_capacity_records)}", state="complete")
                except Exception as e:
                    st.warning(f"Capacity research failed: {e}")

        # 5d: Pricing & hours
        if pplx_pricing and all_names_for_enrichment:
            with st.status(f"💰 Step 5d: Researching pricing & hours...", expanded=True) as status:
                try:
                    pplx_pricing_records = research_pricing_and_hours(
                        perplexity_key, requirement, all_names_for_enrichment
                    )
                    st.write(f"**Got pricing data for {len(pplx_pricing_records)} businesses**")
                    status.update(label=f"✅ Pricing: {len(pplx_pricing_records)}", state="complete")
                except Exception as e:
                    st.warning(f"Pricing research failed: {e}")

    # ── Step 6: Fuzzy merge all sources ──
    with st.status("🔀 Step 6: Merging all data (fuzzy match)...", expanded=True) as status:
        # Primary source: SerpAPI Google Maps (most structured)
        primary = serp_records if serp_records else []

        # All secondary sources
        secondary_lists = [
            s for s in [
                yelp_records,
                local_records,
                pplx_base_records,
                pplx_amenity_records,
                pplx_capacity_records,
                pplx_pricing_records,
            ] if s
        ]

        if primary or secondary_lists:
            if primary:
                final_records = fuzzy_merge_records(primary, *secondary_lists)
            else:
                # No primary — use the first non-empty list as primary
                all_lists = secondary_lists
                final_records = fuzzy_merge_records(all_lists[0], *all_lists[1:]) if all_lists else []
        else:
            final_records = []

        # Deduplicate
        before_dedup = len(final_records)
        final_records = deduplicate_by_name(final_records)

        # Remove internal tracking fields
        for r in final_records:
            r.pop("Data ID", None)
            r.pop("Place ID", None)
            r.pop("Thumbnail", None)

        st.write(f"Merged: {before_dedup} → **{len(final_records)} unique records** after dedup")

        # Show source breakdown
        source_counts = {}
        for r in final_records:
            src = r.get("Data Source", "Unknown")
            source_counts[src] = source_counts.get(src, 0) + 1
        for src, cnt in source_counts.items():
            st.write(f"  • {src}: {cnt}")

        status.update(label=f"✅ {len(final_records)} merged records", state="complete")

    if not final_records:
        st.error("No data found. Try broadening your requirement or checking API keys.")
        st.stop()

    # ── Step 7: Excel ──
    with st.status("📊 Step 7: Pushing to Excel...", expanded=True) as status:
        try:
            filepath = export_to_excel(final_records, requirement)
            st.success(f"`{filepath}`")
            status.update(label="✅ Excel ready", state="complete")
        except Exception as e:
            st.error(f"Export failed: {e}")
            st.stop()

    # ── Done ──
    elapsed = time.time() - t_start
    st.balloons()
    st.markdown("---")

    # Metrics
    cols = st.columns(5)
    with cols[0]:
        st.metric("Records", len(final_records))
    with cols[1]:
        st.metric("Google Maps", len(serp_records))
    with cols[2]:
        pplx_total = len(pplx_base_records) + len(pplx_amenity_records) + len(pplx_capacity_records) + len(pplx_pricing_records)
        st.metric("Perplexity Calls", sum(1 for x in [pplx_base_records, pplx_amenity_records, pplx_capacity_records, pplx_pricing_records] if x))
    with cols[3]:
        other = len(yelp_records) + len(local_records)
        st.metric("Yelp + Local", other)
    with cols[4]:
        st.metric("Time", f"{elapsed:.0f}s")

    # Data
    st.markdown("### Data Preview")
    df = pd.DataFrame(final_records)
    st.dataframe(df, use_container_width=True, height=450)

    # Column stats
    st.markdown("### Column Completeness")
    completeness = {}
    for col in df.columns:
        filled = df[col].notna().sum() - (df[col] == "").sum()
        completeness[col] = f"{filled}/{len(df)} ({filled/len(df)*100:.0f}%)" if len(df) > 0 else "0"
    comp_df = pd.DataFrame([completeness])
    st.dataframe(comp_df, use_container_width=True)

    # Download
    with open(filepath, "rb") as f:
        st.download_button(
            label="⬇️ Download Excel",
            data=f.read(),
            file_name=filepath.split("/")[-1],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )

    st.session_state["result_records"] = final_records
    st.session_state["result_filepath"] = filepath

# ── Previous results ──
elif "result_records" in st.session_state:
    records = st.session_state["result_records"]
    filepath = st.session_state.get("result_filepath", "")

    st.info(f"Previous run — **{len(records)} records**")
    df = pd.DataFrame(records)
    st.dataframe(df, use_container_width=True, height=400)

    if filepath:
        try:
            with open(filepath, "rb") as f:
                st.download_button(
                    label="⬇️ Download Excel",
                    data=f.read(),
                    file_name=filepath.split("/")[-1],
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True,
                )
        except FileNotFoundError:
            st.warning("File not found. Run a new scrape.")
