"""
ClinicalSentinel — InvestiProfile Engine (Feature F7)
Longitudinal investigator behavioral fingerprinting.
Tracks time-of-day entry habits, inter-entry intervals (typing speed/pacing),
and session volumes to flag Behavioral Anomaly Events (BAEs).

Novel contribution: Applies behavioral biometrics paradigm (cybersecurity insider
threat detection) to clinical investigator profiling — a research domain with zero
prior published work (confirmed gap as of 2024 literature review).
"""

import pandas as pd
import numpy as np
import polars as pl
from scipy import stats
from utils import logger


def _hour_distribution(group_df: pd.DataFrame, time_col: str) -> dict:
    """Returns a count of entries per hour-of-day."""
    hours = group_df[time_col].dt.hour
    return hours.value_counts().to_dict()


def _daily_volume(group_df: pd.DataFrame, time_col: str) -> dict:
    """Returns a count of entries per calendar date (as ISO string)."""
    dates = group_df[time_col].dt.date.astype(str)
    return dates.value_counts().to_dict()


def calculate_behavioral_baseline(group_df: pd.DataFrame, time_col: str) -> dict:
    """
    Computes the baseline behavioral fingerprint for an investigator based on the first
    60% of their chronological timeline.
    """
    # 1. Hour of Day Preferences
    hours = group_df[time_col].dt.hour
    hour_dist = hours.value_counts(normalize=True).to_dict()

    # 2. Inter-Entry Intervals (Time between consecutive patient entries)
    sorted_times = group_df[time_col].sort_values()
    time_diffs = sorted_times.diff().dt.total_seconds().dropna()

    # Filter out massive gaps (e.g. overnight) to focus on within-session typing speed
    session_diffs = time_diffs[time_diffs < 3600]  # <1 hour gap

    if len(session_diffs) < 5:
        mean_interval = 0.0
        std_interval = 0.0
    else:
        mean_interval = float(session_diffs.mean())
        std_interval = float(session_diffs.std())

    # 3. Session Volume (patients per day)
    dates = group_df[time_col].dt.date
    daily_counts = dates.value_counts()

    return {
        "preferred_hours": hour_dist,
        "mean_interval_sec": mean_interval,
        "std_interval_sec": std_interval,
        "mean_daily_volume": float(daily_counts.mean()) if len(daily_counts) > 0 else 0.0,
        "std_daily_volume": float(daily_counts.std()) if len(daily_counts) > 1 else 0.0,
    }


def detect_behavioral_anomalies(df: pl.DataFrame, time_col: str, investigator_col: str) -> dict:
    """
    Scans the dataset to detect investigators who broke their own behavioral baselines.
    Returns a dictionary of Behavioral Anomaly Events (BAEs) per investigator.

    Each BAE is a structured dict with:
      - type:        machine-readable anomaly type
      - description: human-readable narrative
      - severity:    "high" | "medium" | "low"
    """
    logger.info("Initializing InvestiProfile Behavioral Fingerprinting (F7)...")
    behavioral_reports: dict = {}

    try:
        pandas_df = df.to_pandas()
        pandas_df[time_col] = pd.to_datetime(pandas_df[time_col], errors="coerce")
        pandas_df = pandas_df.dropna(subset=[time_col, investigator_col])

        if pandas_df.empty:
            return behavioral_reports

        grouped = pandas_df.groupby(investigator_col)

        for investigator, group_df in grouped:
            # Need ≥40 entries to establish a meaningful behavioral fingerprint
            if len(group_df) < 40:
                # Still record basic fingerprint data for visualisation even if below threshold
                entry_hours = _hour_distribution(group_df, time_col)
                daily_volumes = _daily_volume(group_df, time_col)
                behavioral_reports[str(investigator)] = {
                    "investigator_id": str(investigator),
                    "bae_count": 0,
                    "events": [],
                    "entry_hours": entry_hours,
                    "daily_volumes": daily_volumes,
                    "note": "Insufficient data for full behavioral profiling (< 40 entries).",
                }
                continue

            group_df = group_df.sort_values(by=time_col)

            # Split: 60% Baseline, 40% Recent Activity to compare against
            split_idx = int(len(group_df) * 0.6)
            baseline_df = group_df.iloc[:split_idx]
            recent_df = group_df.iloc[split_idx:]

            baseline = calculate_behavioral_baseline(baseline_df, time_col)
            recent = calculate_behavioral_baseline(recent_df, time_col)

            baes = []  # Behavioral Anomaly Events

            # ── CHECK 1: "Night Shift" Anomaly ───────────────────────────────────
            # Flagged if investigator logs data at late-night hours they NEVER worked
            # during the baseline period — the hallmark of retrospective data entry.
            recent_hours = set(recent_df[time_col].dt.hour.unique())
            baseline_hours = set(baseline["preferred_hours"].keys())
            night_violations = [
                h for h in recent_hours
                if h not in baseline_hours and h in {22, 23, 0, 1, 2, 3, 4, 5}
            ]
            if night_violations:
                offending_hours = ", ".join(f"{h:02d}:00" for h in sorted(night_violations))
                baes.append({
                    "type": "NIGHT_SHIFT",
                    "description": (
                        f"Data logged at {offending_hours} — hours completely absent from "
                        f"historical working pattern. Consistent with retrospective bulk entry."
                    ),
                    "severity": "high",
                })

            # ── CHECK 2: "Speed-Typing" Anomaly ──────────────────────────────────
            # Flagged if recent inter-entry interval has dropped >3 std devs below
            # the baseline mean — indicating copy-paste or automated script entry.
            if (
                baseline["std_interval_sec"] > 0
                and recent["mean_interval_sec"] > 0
                and baseline["mean_interval_sec"] > 0
            ):
                z_speed = (
                    baseline["mean_interval_sec"] - recent["mean_interval_sec"]
                ) / baseline["std_interval_sec"]
                if z_speed > 3.0:
                    baes.append({
                        "type": "SPEED_TYPING",
                        "description": (
                            f"Average time between patient entries dropped from "
                            f"{round(baseline['mean_interval_sec'], 1)}s to "
                            f"{round(recent['mean_interval_sec'], 1)}s "
                            f"(z={round(z_speed, 1)}\u03c3). Copy-paste or automated entry highly probable."
                        ),
                        "severity": "high",
                    })

            # ── CHECK 3: "Data Dump" Anomaly ─────────────────────────────────────
            # Flagged if daily patient volume has spiked >3 std devs above baseline.
            # Classic pattern before trial deadline submissions.
            if baseline["std_daily_volume"] > 0:
                z_vol = (
                    recent["mean_daily_volume"] - baseline["mean_daily_volume"]
                ) / baseline["std_daily_volume"]
                if z_vol > 3.0:
                    baes.append({
                        "type": "VOLUME_SPIKE",
                        "description": (
                            f"Daily patient logging rate jumped from "
                            f"{round(baseline['mean_daily_volume'], 1)} to "
                            f"{round(recent['mean_daily_volume'], 1)} patients/day "
                            f"(z={round(z_vol, 1)}\u03c3). Consistent with pre-deadline data fabrication."
                        ),
                        "severity": "medium",
                    })

            # ── CHECK 4: "Weekend Warrior" Anomaly ───────────────────────────────
            # Flagged if a high fraction of recent entries fall on Sat/Sun, but
            # the baseline had very few weekend entries. No patients visit on weekends.
            recent_weekday = recent_df[time_col].dt.dayofweek  # 0=Mon, 6=Sun
            recent_weekend_ratio = (recent_weekday >= 5).mean()
            baseline_weekday = baseline_df[time_col].dt.dayofweek
            baseline_weekend_ratio = (baseline_weekday >= 5).mean()
            if recent_weekend_ratio > 0.25 and (recent_weekend_ratio - baseline_weekend_ratio) > 0.15:
                baes.append({
                    "type": "WEEKEND_WARRIOR",
                    "description": (
                        f"{round(recent_weekend_ratio * 100)}% of recent entries are on weekends "
                        f"(vs {round(baseline_weekend_ratio * 100)}% at baseline). "
                        f"Patients rarely attend clinics on weekends — suggests fabrication."
                    ),
                    "severity": "medium",
                })

            behavioral_reports[str(investigator)] = {
                "investigator_id": str(investigator),
                "bae_count": len(baes),
                "events": baes,
                # Visualization payloads for the frontend heatmaps
                "entry_hours": _hour_distribution(group_df, time_col),
                "daily_volumes": _daily_volume(group_df, time_col),
            }

        flagged = sum(1 for r in behavioral_reports.values() if r["bae_count"] > 0)
        logger.info(
            f"InvestiProfile complete. {flagged} of {len(behavioral_reports)} investigators "
            f"flagged with Behavioral Anomaly Events."
        )
        return behavioral_reports

    except Exception as e:
        logger.warning(f"InvestiProfile engine failed: {e}")
        return {}
