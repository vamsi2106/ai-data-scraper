"""
AI-Powered Data Scraper (v3)
============================
Fully dynamic: RCAFT prompt enhancement drives the entire pipeline.
Works for ANY business type or search scenario.
"""

import time
import streamlit as st
import pandas as pd

from src.prompt_enhancer import enhance_prompt
from src.ai_agent import (
    generate_maps_queries,
    generate_web_search_queries,
    generate_location_info,
    fuzzy_merge_records,
    deduplicate_by_name,
)
from src.serp_search import (
    search_serp_multiple,
    enrich_with_place_details,
    search_google_local,
    search_google_web,
    search_yelp,
)
from src.perplexity_research import (
    research_businesses,
    research_all_field_groups,
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
    .rcaft-card {
        background: #f0f4ff; border: 1px solid #c3d4f7;
        border-radius: 8px; padding: 0.6rem 0.8rem; margin: 0.3rem 0;
    }
    .group-card {
        background: #f7f7f7; border-left: 3px solid #4a90d9;
        padding: 0.5rem 0.8rem; margin: 0.3rem 0; border-radius: 4px;
    }
</style>
""", unsafe_allow_html=True)

# ─── Sidebar ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔑 API Keys")
    if OPENAI_API_KEY and SERPAPI_KEY:
        st.success("Keys loaded from .env")
    else:
        st.info("Set keys in `.env` to persist")
    st.markdown("---")

    openai_key = st.text_input("OpenAI API Key", value=OPENAI_API_KEY, type="password", placeholder="sk-...")
    serpapi_key = st.text_input("SerpAPI Key", value=SERPAPI_KEY, type="password", placeholder="your serpapi key")
    perplexity_key = st.text_input("Perplexity API Key", value=PERPLEXITY_API_KEY, type="password", placeholder="pplx-...")

    st.markdown("---")
    st.markdown("## ⚙️ Settings")

    num_maps_queries = st.slider("Google Maps queries", 1, 6, 4)
    results_per_query = st.slider("Results per Maps query", 10, 80, 40)
    num_web_queries = st.slider("Web search queries (directories)", 1, 8, 5)

    st.markdown("#### SerpAPI Options")
    fetch_place_details = st.checkbox("Fetch Place Details", value=True)
    max_place_details = st.slider("Max place details", 5, 60, 20) if fetch_place_details else 0
    search_yelp_too = st.checkbox("Also search Yelp", value=False)
    search_google_local_too = st.checkbox("Also search Google Local Pack", value=False)

    st.markdown("#### Perplexity Options")
    use_perplexity = st.checkbox("Use Perplexity AI", value=True)
    pplx_discover = st.checkbox("Discover additional businesses", value=True)
    pplx_enrich = st.checkbox("Enrich with dynamic field groups", value=True,
                               help="AI decides what categories of info to research based on your query")

    st.markdown("---")
    st.markdown("### Pipeline")
    st.markdown("""
    **0.** RCAFT prompt enhancement (dynamic)
    1. AI keyword strategy (Maps + Web)
    2. SerpAPI → Google Maps
    3. SerpAPI → Place Details
    4. SerpAPI → Web search (directories/reviews)
    5. Yelp + Local *(optional)*
    6. Perplexity → Discover + **Dynamic enrichment**
    7. Fuzzy merge → Excel
    """)

# ─── Main ─────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>🔍 AI Data Scraper v3</h1>
    <p>Fully dynamic — tell it what you need, AI figures out the rest</p>
</div>
""", unsafe_allow_html=True)

raw_requirement = st.text_area(
    "📝 What data do you need?",
    placeholder="Examples:\n"
    "• All spas in Hyderabad with amenities, pricing, room capacity\n"
    "• Top restaurants in Mumbai with menu, seating capacity, delivery options\n"
    "• IT companies in Bangalore with tech stack, team size, clients\n"
    "• Gyms in Delhi with equipment, membership plans, trainers",
    height=120,
)

# ─── Two-step flow ────────────────────────────────────────────────────
btn_col1, btn_col2, _ = st.columns([1.2, 1.2, 3])
with btn_col1:
    enhance_btn = st.button("✨ Enhance Prompt", width="stretch")
with btn_col2:
    start_btn = st.button("🚀 Search Data", type="primary", width="stretch")

st.markdown("---")

if "enhanced_data" not in st.session_state:
    st.session_state["enhanced_data"] = None

# ═══════════════════════════════════════════════════════════════════════
# ENHANCE PROMPT
# ═══════════════════════════════════════════════════════════════════════
if enhance_btn:
    if not openai_key:
        st.error("Enter your OpenAI API key in the sidebar.")
        st.stop()
    if not raw_requirement.strip():
        st.error("Type your requirement first.")
        st.stop()

    with st.spinner("✨ Enhancing with RCAFT framework..."):
        try:
            enhanced = enhance_prompt(openai_key, raw_requirement)
            st.session_state["enhanced_data"] = enhanced
        except Exception as e:
            st.error(f"Enhancement failed: {e}")
            st.stop()

# ── Display enhanced prompt ───────────────────────────────────────────
if st.session_state.get("enhanced_data"):
    enhanced = st.session_state["enhanced_data"]
    rcaft = enhanced.get("rcaft", {})
    enhanced_prompt_text = enhanced.get("enhanced_prompt", raw_requirement)
    search_keywords = enhanced.get("search_keywords", [])
    data_fields = enhanced.get("data_fields", [])
    target_sources = enhanced.get("target_sources", [])
    field_groups = enhanced.get("field_groups", [])
    domain = enhanced.get("domain", "")

    st.markdown("### ✨ RCAFT-Enhanced Prompt")
    if domain:
        st.markdown(f"**Detected domain:** {domain}")

    # RCAFT breakdown
    r_cols = st.columns(5)
    for col, label, key in zip(r_cols,
        ["🎭 Role", "📋 Context", "⚡ Action", "📐 Format", "🎯 Tone"],
        ["role", "context", "action", "format", "tone"]):
        with col:
            st.markdown(f"**{label}**")
            st.caption(str(rcaft.get(key, "—"))[:150])

    # Editable enhanced prompt
    edited_prompt = st.text_area(
        "📝 Enhanced Prompt (edit if needed, then click Search Data)",
        value=enhanced_prompt_text, height=140, key="edited_enhanced_prompt",
    )
    st.session_state["enhanced_data"]["enhanced_prompt"] = edited_prompt

    # Keywords, fields, sources
    info_cols = st.columns(3)
    with info_cols[0]:
        if search_keywords:
            st.markdown(f"**🔑 Keywords ({len(search_keywords)})**")
            st.caption(", ".join(search_keywords[:10]))
    with info_cols[1]:
        if data_fields:
            st.markdown(f"**📊 Data Fields ({len(data_fields)})**")
            st.caption(", ".join(data_fields[:12]))
    with info_cols[2]:
        if target_sources:
            st.markdown(f"**🌐 Sources ({len(target_sources)})**")
            st.caption(", ".join(target_sources[:8]))

    # Dynamic field groups preview
    if field_groups:
        st.markdown(f"#### 🔬 Research Groups ({len(field_groups)} dynamic categories)")
        for g in field_groups:
            gname = g.get("group_name", "?")
            gfields = g.get("fields", [])
            gprompt = g.get("research_prompt", "")
            with st.expander(f"**{gname}** — {', '.join(gfields[:5])}"):
                st.write(f"**Fields:** {', '.join(gfields)}")
                st.write(f"**Research focus:** {gprompt[:300]}")

    st.markdown("---")


# ═══════════════════════════════════════════════════════════════════════
# SEARCH DATA (full pipeline)
# ═══════════════════════════════════════════════════════════════════════
if start_btn:
    if not openai_key:
        st.error("Enter your OpenAI API key.")
        st.stop()
    if not serpapi_key:
        st.error("Enter your SerpAPI key.")
        st.stop()
    if use_perplexity and not perplexity_key:
        st.error("Enter your Perplexity API key (or uncheck Perplexity).")
        st.stop()
    if not raw_requirement.strip():
        st.error("Describe what data you need.")
        st.stop()

    t_start = time.time()
    serp_records = []
    web_search_results = []
    yelp_records = []
    local_records = []
    pplx_base_records = []
    pplx_group_records = {}  # { group_name: [records] }

    # ── Get or create enhanced data ──
    if st.session_state.get("enhanced_data"):
        edata = st.session_state["enhanced_data"]
        requirement = edata.get("enhanced_prompt", raw_requirement)
        search_keywords = edata.get("search_keywords", [])
        data_fields = edata.get("data_fields", [])
        target_sources = edata.get("target_sources", [])
        field_groups = edata.get("field_groups", [])
        st.success("Using your RCAFT-enhanced prompt ✨")
    else:
        with st.status("✨ Step 0: Auto-enhancing with RCAFT...", expanded=True) as status:
            try:
                edata = enhance_prompt(openai_key, raw_requirement)
                requirement = edata.get("enhanced_prompt", raw_requirement)
                search_keywords = edata.get("search_keywords", [])
                data_fields = edata.get("data_fields", [])
                target_sources = edata.get("target_sources", [])
                field_groups = edata.get("field_groups", [])

                rcaft = edata.get("rcaft", {})
                rc = st.columns(5)
                for col, lbl, k in zip(rc,
                    ["🎭 Role", "📋 Context", "⚡ Action", "📐 Format", "🎯 Tone"],
                    ["role", "context", "action", "format", "tone"]):
                    with col:
                        st.markdown(f"**{lbl}**")
                        st.caption(str(rcaft.get(k, "—"))[:120])

                st.info(requirement[:400])

                if field_groups:
                    st.write(f"**Dynamic research groups:** {', '.join(g.get('group_name','') for g in field_groups)}")

                status.update(label="✅ RCAFT enhancement done", state="complete")
            except Exception as e:
                st.warning(f"Enhancement failed: {e}. Using original input.")
                requirement = raw_requirement
                search_keywords = [raw_requirement]
                data_fields = []
                target_sources = []
                field_groups = []

    # ══════════════════════════════════════════════════════════════════
    # STEP 1: AI Keyword Strategy + Location
    # ══════════════════════════════════════════════════════════════════
    with st.status("🧠 Step 1: AI generating search queries...", expanded=True) as status:
        try:
            loc = generate_location_info(openai_key, requirement)
            lat = loc.get("latitude")
            lng = loc.get("longitude")
            city = loc.get("city", "")
            yelp_loc = loc.get("yelp_location", city)
            if lat and lng:
                st.write(f"📍 **{city}** ({lat}, {lng})")

            maps_queries = generate_maps_queries(
                openai_key, requirement, search_keywords, city, num_queries=num_maps_queries
            )
            for i, q in enumerate(maps_queries, 1):
                st.write(f"  🗺️ {i}. `{q}`")

            web_queries = generate_web_search_queries(
                openai_key, requirement, search_keywords, city, target_sources, num_queries=num_web_queries
            )
            for i, q in enumerate(web_queries, 1):
                st.write(f"  🌐 {i}. `{q}`")

            status.update(label=f"✅ {len(maps_queries)} Maps + {len(web_queries)} Web queries", state="complete")
        except Exception as e:
            st.error(f"Query generation failed: {e}")
            st.stop()

    # ══════════════════════════════════════════════════════════════════
    # STEP 2: SerpAPI Google Maps
    # ══════════════════════════════════════════════════════════════════
    with st.status("🗺️ Step 2: Google Maps listings...", expanded=True) as status:
        try:
            serp_records = search_serp_multiple(
                maps_queries, serpapi_key, results_per_query=results_per_query,
                lat=lat, lng=lng,
            )
            st.write(f"**{len(serp_records)} unique businesses from Google Maps**")
            if serp_records:
                st.write("Preview: " + ", ".join(r.get("Name", "?") for r in serp_records[:8]) + "...")
            status.update(label=f"✅ {len(serp_records)} from Maps", state="complete")
        except Exception as e:
            st.warning(f"Google Maps failed: {e}")

    # ══════════════════════════════════════════════════════════════════
    # STEP 3: Place Details
    # ══════════════════════════════════════════════════════════════════
    if fetch_place_details and serp_records and max_place_details > 0:
        with st.status(f"🏢 Step 3: Place Details ({max_place_details} places)...", expanded=True) as status:
            progress = st.progress(0)
            log = st.empty()

            def _cb(cur, tot, name):
                progress.progress(cur / tot if tot > 0 else 0)
                log.write(f"  [{cur+1}/{tot}] {name}")

            try:
                serp_records = enrich_with_place_details(
                    serp_records, serpapi_key, max_places=max_place_details, progress_callback=_cb,
                )
                progress.progress(1.0)
                status.update(label="✅ Place Details enriched", state="complete")
            except Exception as e:
                st.warning(f"Place Details failed: {e}")

    # ══════════════════════════════════════════════════════════════════
    # STEP 4: Web Search (directories, reviews, third-party)
    # ══════════════════════════════════════════════════════════════════
    with st.status("🌐 Step 4: Searching directories & review sites...", expanded=True) as status:
        try:
            web_search_results = search_google_web(
                web_queries, serpapi_key, location=city, results_per_query=10,
            )
            st.write(f"**{len(web_search_results)} third-party pages found**")
            for r in web_search_results[:5]:
                st.write(f"  • [{r.get('Source Domain', '')}] {r.get('Title', '')[:70]}")
            status.update(label=f"✅ {len(web_search_results)} directory pages", state="complete")
        except Exception as e:
            st.warning(f"Web search failed: {e}")

    # ══════════════════════════════════════════════════════════════════
    # STEP 5: Yelp + Local (optional)
    # ══════════════════════════════════════════════════════════════════
    if search_yelp_too and yelp_loc:
        with st.status("🔎 Step 5a: Yelp...", expanded=True) as status:
            try:
                yelp_records = search_yelp(maps_queries[0], serpapi_key, location=yelp_loc)
                st.write(f"**{len(yelp_records)} from Yelp**")
                status.update(label=f"✅ {len(yelp_records)} from Yelp", state="complete")
            except Exception as e:
                st.warning(f"Yelp failed: {e}")

    if search_google_local_too:
        with st.status("📍 Step 5b: Local Pack...", expanded=True) as status:
            try:
                for q in maps_queries[:2]:
                    local_records.extend(search_google_local(q, serpapi_key, location=city))
                st.write(f"**{len(local_records)} from Local Pack**")
                status.update(label=f"✅ {len(local_records)} from Local", state="complete")
            except Exception as e:
                st.warning(f"Local failed: {e}")

    # ══════════════════════════════════════════════════════════════════
    # STEP 6: Perplexity — Dynamic Research
    # ══════════════════════════════════════════════════════════════════
    all_names = [r.get("Name", "") for r in serp_records + yelp_records + local_records if r.get("Name")]

    # Build web context for Perplexity
    web_context = ""
    if web_search_results:
        snippets = [f"- {r.get('Title','')}: {r.get('Snippet','')}" for r in web_search_results[:15]]
        web_context = "\n\nRelevant web sources:\n" + "\n".join(snippets)

    pplx_req = requirement + web_context

    if use_perplexity and perplexity_key:
        # 6a: Discover additional businesses
        if pplx_discover:
            with st.status("🔬 Step 6a: Discovering additional businesses...", expanded=True) as status:
                try:
                    pplx_base_records = research_businesses(
                        perplexity_key, pplx_req, data_fields=data_fields, existing_names=all_names
                    )
                    st.write(f"**+{len(pplx_base_records)} additional businesses**")
                    status.update(label=f"✅ +{len(pplx_base_records)} discovered", state="complete")
                except Exception as e:
                    st.warning(f"Discovery failed: {e}")

        # Collect all names for enrichment
        all_names_for_enrichment = list(set(
            all_names + [r.get("Name", "") for r in pplx_base_records if r.get("Name")]
        ))

        # 6b: Dynamic field group enrichment
        if pplx_enrich and field_groups and all_names_for_enrichment:
            st.markdown(f"#### 🔬 Researching {len(field_groups)} dynamic categories...")

            for idx, group in enumerate(field_groups):
                gname = group.get("group_name", f"Group {idx+1}")
                gfields = group.get("fields", [])
                gprompt = group.get("research_prompt", "")

                if not gfields:
                    continue

                with st.status(
                    f"📊 Step 6.{idx+2}: {gname} ({len(all_names_for_enrichment)} businesses)...",
                    expanded=True
                ) as status:
                    try:
                        from src.perplexity_research import research_field_group
                        records = research_field_group(
                            perplexity_key, pplx_req, all_names_for_enrichment,
                            gname, gfields, gprompt,
                        )
                        pplx_group_records[gname] = records
                        st.write(f"**{gname}: data for {len(records)} businesses**")
                        st.write(f"Fields: {', '.join(gfields[:6])}")
                        status.update(label=f"✅ {gname}: {len(records)} records", state="complete")
                    except Exception as e:
                        st.warning(f"{gname} failed: {e}")
                        pplx_group_records[gname] = []

    # ══════════════════════════════════════════════════════════════════
    # STEP 7: Fuzzy merge + Excel
    # ══════════════════════════════════════════════════════════════════
    with st.status("🔀 Step 7: Merging all data...", expanded=True) as status:
        primary = serp_records if serp_records else []

        # Flatten all Perplexity group results into secondary lists
        secondary_lists = [s for s in [yelp_records, local_records, pplx_base_records] if s]
        for gname, grecords in pplx_group_records.items():
            if grecords:
                secondary_lists.append(grecords)

        if primary or secondary_lists:
            if primary:
                final_records = fuzzy_merge_records(primary, *secondary_lists)
            else:
                all_lists = secondary_lists
                final_records = fuzzy_merge_records(all_lists[0], *all_lists[1:]) if all_lists else []
        else:
            final_records = []

        before_dedup = len(final_records)
        final_records = deduplicate_by_name(final_records)

        # Remove internal tracking fields
        for r in final_records:
            r.pop("Data ID", None)
            r.pop("Place ID", None)
            r.pop("Thumbnail", None)

        st.write(f"**{before_dedup} → {len(final_records)} unique records**")

        source_counts = {}
        for r in final_records:
            src = r.get("Data Source", "Unknown")
            source_counts[src] = source_counts.get(src, 0) + 1
        for src, cnt in source_counts.items():
            st.write(f"  • {src}: {cnt}")

        # Show field coverage
        if final_records:
            all_fields = set()
            for r in final_records:
                all_fields.update(r.keys())
            st.write(f"  • **{len(all_fields)} total fields** collected across all records")

        status.update(label=f"✅ {len(final_records)} records merged", state="complete")

    if not final_records:
        st.error("No data found. Try broadening your requirement.")
        st.stop()

    with st.status("📊 Exporting to Excel...", expanded=True) as status:
        try:
            filepath = export_to_excel(final_records, raw_requirement)
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
    metric_cols = st.columns(5)
    with metric_cols[0]:
        st.metric("Total Records", len(final_records))
    with metric_cols[1]:
        st.metric("Google Maps", len(serp_records))
    with metric_cols[2]:
        st.metric("Web Pages", len(web_search_results))
    with metric_cols[3]:
        enrich_groups = sum(1 for v in pplx_group_records.values() if v)
        st.metric("Enrichment Groups", enrich_groups)
    with metric_cols[4]:
        st.metric("Time", f"{elapsed:.0f}s")

    # Data preview
    st.markdown("### Data Preview")
    df = pd.DataFrame(final_records).astype(str).replace("None", "")
    st.dataframe(df, width="stretch", height=450)

    # Column completeness
    st.markdown("### Column Completeness")
    completeness = {}
    for col in df.columns:
        filled = df[col].notna().sum() - (df[col] == "").sum()
        completeness[col] = f"{filled}/{len(df)} ({filled/len(df)*100:.0f}%)" if len(df) > 0 else "0"
    st.dataframe(pd.DataFrame([completeness]), width="stretch")

    # Download
    with open(filepath, "rb") as f:
        st.download_button(
            label="⬇️ Download Excel", data=f.read(),
            file_name=filepath.split("/")[-1],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary", width="stretch",
        )

    st.session_state["result_records"] = final_records
    st.session_state["result_filepath"] = filepath

# ── Previous results ──
elif "result_records" in st.session_state:
    records = st.session_state["result_records"]
    filepath = st.session_state.get("result_filepath", "")

    st.info(f"Previous run — **{len(records)} records**")
    df = pd.DataFrame(records).astype(str).replace("None", "")
    st.dataframe(df, width="stretch", height=400)

    if filepath:
        try:
            with open(filepath, "rb") as f:
                st.download_button(
                    label="⬇️ Download Excel", data=f.read(),
                    file_name=filepath.split("/")[-1],
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary", width="stretch",
                )
        except FileNotFoundError:
            st.warning("File not found. Run a new scrape.")
