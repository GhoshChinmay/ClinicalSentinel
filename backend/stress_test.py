"""
DataSentinel — Full Stress Test with creditcard.csv
Tests all API endpoints end-to-end.
"""

import requests
import time
import json
import polars as pl

BASE = "http://localhost:8000"
CSV_PATH = "data/creditcard.csv"


def banner(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def inspect_dataset():
    banner("PHASE 0: DATASET INSPECTION")
    df = pl.read_csv(CSV_PATH, n_rows=5, infer_schema_length=10000)
    full = pl.scan_csv(CSV_PATH).collect()
    print(f"Shape: {full.shape[0]} rows x {full.shape[1]} cols")
    print(f"Columns: {full.columns}")
    print(f"Dtypes: {dict(zip(full.columns[:10], [str(d) for d in full.dtypes[:10]]))}")
    print(f"Null counts: {dict(zip(full.columns[:10], [full[c].null_count() for c in full.columns[:10]]))}")
    print(f"Sample:\n{df}")
    return full.shape


def test_upload():
    banner("TEST 1: UPLOAD creditcard.csv")
    start = time.time()
    with open(CSV_PATH, "rb") as f:
        resp = requests.post(
            f"{BASE}/api/upload/",
            files={"file": ("creditcard.csv", f, "text/csv")},
            timeout=300,
        )
    elapsed = time.time() - start
    print(f"Status: {resp.status_code} | Time: {elapsed:.2f}s")

    if resp.status_code != 200:
        print(f"FATAL ERROR: {resp.text[:1000]}")
        return None

    data = resp.json()
    print(json.dumps(data, indent=2))
    return data.get("session_id")


def test_get_data(session_id):
    banner("TEST 2: GET RAW DATA")
    start = time.time()
    resp = requests.get(f"{BASE}/api/data/{session_id}", timeout=120)
    elapsed = time.time() - start
    print(f"Status: {resp.status_code} | Time: {elapsed:.2f}s")
    if resp.status_code == 200:
        d = resp.json()
        print(f"Rows returned: {len(d.get('data', []))}")
        print(f"Anomalies: {d.get('total_anomalies')}")
    else:
        print(f"ERROR: {resp.text[:500]}")
    return resp.status_code


def test_anomalies_only(session_id):
    banner("TEST 3: GET ANOMALIES ONLY")
    start = time.time()
    resp = requests.get(f"{BASE}/api/data/{session_id}?only_anomalies=true", timeout=120)
    elapsed = time.time() - start
    print(f"Status: {resp.status_code} | Time: {elapsed:.2f}s")
    if resp.status_code == 200:
        d = resp.json()
        print(f"Anomaly rows: {len(d.get('data', []))}")
    else:
        print(f"ERROR: {resp.text[:500]}")
    return resp.status_code


def test_visualization(session_id, label="TEST 4: VISUALIZATION (pre-clean)"):
    banner(label)
    start = time.time()
    resp = requests.get(f"{BASE}/api/viz/{session_id}", timeout=120)
    elapsed = time.time() - start
    print(f"Status: {resp.status_code} | Time: {elapsed:.2f}s")
    if resp.status_code == 200:
        viz = resp.json()
        print(f"Numeric cols: {len(viz.get('columns', []))}")
        print(f"Cat cols: {len(viz.get('categorical_columns', []))}")
        print(f"Correlation: {'yes' if viz.get('correlation') else 'no'}")
        print(f"Health score: {viz.get('health_score')}")
        print(f"Raw histogram bins: {len(viz.get('global_raw_hist', []))}")
        if viz.get("global_clean_hist"):
            print(f"Clean histogram bins: {len(viz['global_clean_hist'])}")
        if viz.get("categorical_data"):
            print(f"Categorical charts: {len(viz['categorical_data'])}")
        print(f"Clean sample rows: {len(viz.get('clean_sample', []))}")
    else:
        print(f"ERROR: {resp.text[:500]}")
    return resp.status_code


def test_insights(session_id):
    banner("TEST 5: AI INSIGHTS ENGINE")
    start = time.time()
    resp = requests.get(f"{BASE}/api/insights/{session_id}", timeout=300)
    elapsed = time.time() - start
    print(f"Status: {resp.status_code} | Time: {elapsed:.2f}s")
    if resp.status_code == 200:
        ins = resp.json()
        insights = ins.get("insights", [])
        print(f"Insights returned: {len(insights)}")
        for i, item in enumerate(insights):
            obs = item.get("observation", "")[:100]
            ins_text = item.get("insight", "")[:100]
            act = item.get("action", "")[:100]
            print(f"  [{i+1}] OBS: {obs}")
            print(f"       INS: {ins_text}")
            print(f"       ACT: {act}")
    else:
        print(f"ERROR: {resp.text[:500]}")
    return resp.status_code


def test_clean(session_id, action="quarantine"):
    banner(f"TEST 6: CLEANING ({action.upper()})")
    start = time.time()
    resp = requests.post(f"{BASE}/api/clean/{session_id}?action={action}", timeout=120)
    elapsed = time.time() - start
    print(f"Status: {resp.status_code} | Time: {elapsed:.2f}s")
    if resp.status_code == 200:
        c = resp.json()
        print(f"Action: {c.get('action_taken')}")
        print(f"Original rows: {c.get('original_rows')}")
        print(f"Cleaned rows: {c.get('new_total')}")
        removed = c.get('original_rows', 0) - c.get('new_total', 0)
        print(f"Rows removed: {removed}")
    else:
        print(f"ERROR: {resp.text[:500]}")
    return resp.status_code


def test_compare(session_id):
    banner("TEST 7: COMPARE RAW vs CLEANED")
    start = time.time()
    resp = requests.get(f"{BASE}/api/compare/{session_id}", timeout=120)
    elapsed = time.time() - start
    print(f"Status: {resp.status_code} | Time: {elapsed:.2f}s")
    if resp.status_code == 200:
        cmp = resp.json()
        print(f"Is dropped: {cmp.get('is_dropped')}")
        print(f"Clean count: {cmp.get('count')}")
        print(f"Original sample: {len(cmp.get('original', []))} rows")
        print(f"Cleaned sample: {len(cmp.get('cleaned', []))} rows")
    else:
        print(f"ERROR: {resp.text[:500]}")
    return resp.status_code


def test_quarantine(session_id):
    banner("TEST 8: QUARANTINE VAULT")
    start = time.time()
    resp = requests.get(f"{BASE}/api/quarantine/{session_id}", timeout=120)
    elapsed = time.time() - start
    print(f"Status: {resp.status_code} | Time: {elapsed:.2f}s")
    if resp.status_code == 200:
        q = resp.json()
        print(f"Quarantined rows: {q.get('count')}")
    else:
        print(f"ERROR: {resp.text[:500]}")
    return resp.status_code


def test_download(session_id, source="cleaned"):
    banner(f"TEST 10: DOWNLOAD ({source.upper()})")
    start = time.time()
    resp = requests.get(f"{BASE}/api/download/{session_id}?source={source}", timeout=120)
    elapsed = time.time() - start
    print(f"Status: {resp.status_code} | Time: {elapsed:.2f}s")
    if resp.status_code == 200:
        size_mb = len(resp.content) / (1024 * 1024)
        lines = resp.text.split("\n")
        print(f"File size: {size_mb:.1f} MB")
        print(f"CSV lines: {len(lines)}")
        print(f"Header: {lines[0][:120]}")
    else:
        print(f"ERROR: {resp.text[:500]}")
    return resp.status_code


def main():
    print("\n" + "#" * 60)
    print("#  DataSentinel STRESS TEST - creditcard.csv")
    print("#" * 60)

    shape = inspect_dataset()
    results = {}

    session_id = test_upload()
    if not session_id:
        print("\nFATAL: Upload failed. Aborting.")
        return

    results["upload"] = "PASS"

    for name, fn in [
        ("get_data", lambda: test_get_data(session_id)),
        ("anomalies_only", lambda: test_anomalies_only(session_id)),
        ("visualization", lambda: test_visualization(session_id)),
        ("insights", lambda: test_insights(session_id)),
        ("clean", lambda: test_clean(session_id, "quarantine")),
        ("compare", lambda: test_compare(session_id)),
        ("quarantine", lambda: test_quarantine(session_id)),
        ("viz_post_clean", lambda: test_visualization(session_id, "TEST 9: VIZ AFTER CLEANING")),
        ("download_cleaned", lambda: test_download(session_id, "cleaned")),
        ("download_quarantine", lambda: test_download(session_id, "quarantine")),
    ]:
        status = fn()
        results[name] = "PASS" if status == 200 else f"FAIL ({status})"

    banner("FINAL RESULTS")
    passed = sum(1 for v in results.values() if v == "PASS")
    total = len(results)
    print(f"\nDataset: creditcard.csv ({shape[0]} rows x {shape[1]} cols)")
    print(f"Results: {passed}/{total} passed\n")
    for test, result in results.items():
        icon = "PASS" if result == "PASS" else "FAIL"
        print(f"  [{icon}] {test}")

    if passed == total:
        print(f"\nALL {total} TESTS PASSED!")
    else:
        print(f"\n{total - passed} TEST(S) FAILED!")


if __name__ == "__main__":
    main()
