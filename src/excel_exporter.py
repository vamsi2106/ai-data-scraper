"""Simple Excel export – just push data to a sheet, no fancy formatting."""

import os
from datetime import datetime
import pandas as pd
from src.config import OUTPUT_DIR


def export_to_excel(records: list[dict], requirement: str = "", filename: str | None = None) -> str:
    """Export records to Excel. Simple. Just data."""
    if not filename:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_req = "".join(c if c.isalnum() or c in " _-" else "" for c in requirement[:40]).strip().replace(" ", "_")
        filename = f"data_{safe_req}_{ts}.xlsx"

    filepath = os.path.join(OUTPUT_DIR, filename)
    df = pd.DataFrame(records)

    if df.empty:
        df = pd.DataFrame(columns=["No Data Found"])

    df.to_excel(filepath, index=False, engine="openpyxl")
    return filepath
