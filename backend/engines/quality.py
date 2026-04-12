import polars as pl
import os
from utils import _session_dir, logger


def generate_quality_report(session_id: str) -> dict:
    session_dir = _session_dir(session_id)
    cleaned_parquet_path = f"{session_dir}/cleaned_data.parquet"

    if not os.path.exists(cleaned_parquet_path):
        return {"error": "Cleaned dataset not found."}

    df = pl.read_parquet(cleaned_parquet_path)

    rows = len(df)
    columns = len(df.columns)

    if rows == 0:
        return {"error": "Dataset is empty."}

    # Missing values
    try:
        null_counts = sum(
            v[0] for v in df.null_count().to_dict(as_series=False).values()
        )
        missing_ratio = null_counts / (rows * columns)
    except Exception:
        missing_ratio = 0

    # Duplicate ratio
    try:
        unique_rows = len(df.unique())
        duplicate_ratio = (rows - unique_rows) / rows
    except Exception:
        duplicate_ratio = 0

    # Imbalance: Find categorical columns
    imbalance_warnings = []
    try:
        # BUG-05 FIX: Use pl.String directly (Polars ≥0.20 no longer has pl.Utf8)
        categorical_cols = [
            c
            for c, dt in zip(df.columns, df.dtypes)
            if str(dt) in ("String", "Utf8", "Categorical")
        ]
        for c in categorical_cols:
            counts = df[c].value_counts().sort("count", descending=True)
            if len(counts) > 1 and len(counts) <= 10:
                top_ratio = counts["count"][0] / rows
                if top_ratio > 0.90:
                    imbalance_warnings.append(
                        f"Column '{c}' is highly imbalanced ({top_ratio*100:.1f}% single category)."
                    )
    except Exception as e:
        logger.warning("Error checking imbalance: %s", e)

    quality_score = (
        100
        - (missing_ratio * 40)
        - (duplicate_ratio * 30)
        - (len(imbalance_warnings) * 5)
    )
    quality_score = max(0, min(100, quality_score))

    readiness = (
        "Production Ready"
        if quality_score >= 85
        else "Needs Review" if quality_score >= 60 else "Not Ready"
    )

    report = {
        "status": "success",
        "score": round(quality_score, 1),
        "readiness": readiness,
        "metrics": {
            "Rows": rows,
            "Columns": columns,
            "Missing Value Ratio": f"{missing_ratio*100:.2f}%",
            "Duplicate Row Ratio": f"{duplicate_ratio*100:.2f}%",
        },
        "imbalance_warnings": imbalance_warnings,
    }

    return report
