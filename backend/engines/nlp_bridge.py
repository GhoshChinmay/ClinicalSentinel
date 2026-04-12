"""
DataSentinel — NLP Bridge Engine
Converts unstructured text columns into numeric features via TF-IDF + PCA.
"""

import polars as pl
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from utils import logger


def process_text_anomalies(df: pl.DataFrame) -> pl.DataFrame:
    """Extract structural and semantic features from text columns."""
    string_cols = [
        col
        for col, dtype in zip(df.columns, df.dtypes)
        if dtype in [pl.Utf8, getattr(pl, "String", pl.Utf8)]
    ]

    if not string_cols:
        return df

    logger.info(
        "Auto-detected %d text columns. Running Universal NLP Bridge...",
        len(string_cols),
    )

    new_features = []

    # --- PHASE A: STRUCTURAL SHAPE EXTRACTION ---
    for col in string_cols:
        df = df.with_columns(pl.col(col).fill_null(""))
        safe_len = pl.col(col).str.len_chars() + 0.0001

        new_features.extend(
            [
                pl.col(col).str.len_chars().alias(f"{col}_length"),
                (pl.col(col).str.count_matches(r"\d") / safe_len).alias(
                    f"{col}_digit_ratio"
                ),
                (pl.col(col).str.count_matches(r"[A-Z]") / safe_len).alias(
                    f"{col}_upper_ratio"
                ),
                (pl.col(col).str.count_matches(r"[^\w\s]") / safe_len).alias(
                    f"{col}_special_ratio"
                ),
            ]
        )

    df = df.with_columns(new_features)

    # --- PHASE B: TF-IDF + PCA (THE NLP BRIDGE) ---
    if len(df) >= 100:
        df = df.with_columns(
            pl.concat_str([pl.col(c) for c in string_cols], separator=" ").alias(
                "meta_text"
            )
        )

        text_data = df["meta_text"].to_list()
        vectorizer = TfidfVectorizer(max_features=500, stop_words="english")

        try:
            tfidf_matrix = vectorizer.fit_transform(text_data)
            n_comps = min(3, tfidf_matrix.shape[1])
            if n_comps > 0:
                svd = TruncatedSVD(n_components=n_comps, random_state=42)
                pca_features = svd.fit_transform(tfidf_matrix)
                pca_cols = [
                    pl.Series(f"nlp_pc{i+1}", pca_features[:, i])
                    for i in range(n_comps)
                ]
                df = df.with_columns(pca_cols)
        except Exception as e:
            logger.warning("NLP Engine Warning: %s", e)

        df = df.drop("meta_text")

    return df
