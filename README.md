# AI Data Scraper

Pulls business data from **Google Maps + Yelp + Perplexity AI** and dumps it into Excel.

---

## Quick Start (3 steps)

### 1. Install

```bash
cd /Users/apple/Documents/new-proj
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Add your API keys to `.env`

Open the `.env` file and fill in your keys. They persist across restarts — no need to paste them every time.

```
OPENAI_API_KEY=sk-your-key-here
SERPAPI_KEY=your-serpapi-key-here
PERPLEXITY_API_KEY=pplx-your-key-here
```

Where to get keys:
- **OpenAI**: https://platform.openai.com/api-keys
- **SerpAPI**: https://serpapi.com (100 free searches/month)
- **Perplexity**: https://docs.perplexity.ai

### 3. Run

```bash
source venv/bin/activate
streamlit run app.py
```

Opens at **http://localhost:8501**. Your API keys auto-load from `.env`.

---

## How to Use

1. Open the app in your browser
2. API keys are pre-filled from `.env` (green checkmark in sidebar)
3. Type what data you need in the text box, e.g.:
   > All spas in Hyderabad with amenities, room capacity, manpower, pricing, contact info
4. Adjust settings in the sidebar if you want (defaults are good)
5. Click **Get Data**
6. Watch the pipeline run, then download the Excel file

---

## What the Pipeline Does

| Step | Source | What it gets |
|------|--------|-------------|
| 1 | OpenAI | Generates search queries + detects city coordinates |
| 2 | SerpAPI → Google Maps | Business listings: name, address, phone, rating, website, hours |
| 3 | SerpAPI → Place Details | Per-business: amenities, reviews, service options, popular times |
| 4 | SerpAPI → Yelp *(opt)* | Yelp ratings, review snippets, price range |
| 5 | Perplexity → Discovery | Finds businesses not on Google Maps |
| 6 | Perplexity → Amenities | Services, facilities, amenities per business |
| 7 | Perplexity → Capacity | Room capacity, staff count, area size |
| 8 | Perplexity → Pricing | Price range, packages, operating hours |
| 9 | Fuzzy Merge | Matches "Tattva Spa" = "Tattva Wellness Spa" and combines all fields |
| 10 | Excel | Dumps everything to `.xlsx` |

---

## Settings Explained

### SerpAPI Options
- **Search queries** (1-6): More queries = more businesses found (costs 1 credit each)
- **Results per query** (10-80): How many businesses per search
- **Place Details**: Deep lookup per business. Uses 1 credit each. Gets reviews, amenities, hours
- **Yelp**: Extra source. 1 credit total
- **Google Local Pack**: Extra source. 1 credit per query

### Perplexity Options
- **Discover businesses**: Finds ones not in Google Maps
- **Amenities & services**: What each business offers
- **Capacity & staffing**: Room count, staff count
- **Pricing & hours**: Price ranges, packages, schedules

### Cost Estimate (per run, defaults)
- SerpAPI: ~3 credits (3 queries) + ~20 credits (place details) = **~23 credits**
- Perplexity: ~4-6 API calls = **~$0.02-0.05**
- OpenAI: ~2 calls = **~$0.01**

---

## Project Structure

```
new-proj/
├── app.py                       # Streamlit UI + pipeline
├── .env                         # Your API keys (persisted)
├── requirements.txt             # Dependencies
├── output/                      # Excel files saved here
└── src/
    ├── config.py                # Loads .env keys
    ├── ai_agent.py              # Query gen + fuzzy merge
    ├── serp_search.py           # Google Maps + Place Details + Yelp
    ├── perplexity_research.py   # sonar-pro focused research calls
    └── excel_exporter.py        # Simple Excel dump
```

---

## Troubleshooting

**App won't start**: Make sure you activated the venv: `source venv/bin/activate`

**Keys not loading**: Check `.env` is in the project root (`/Users/apple/Documents/new-proj/.env`)

**SerpAPI returns 0 results**: Check your key at https://serpapi.com/account — free tier = 100/month

**Perplexity errors**: Check your key at https://docs.perplexity.ai — make sure you have credits

**Excel is empty**: Check the logs in the app — one of the API calls likely failed
