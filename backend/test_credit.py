import time
import sys
import os
import uuid

os.environ["LOKY_MAX_CPU_COUNT"] = "4"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from engines.detection import process_and_detect

start = time.time()
print("Starting processing of creditcard.csv...")
res = process_and_detect(file_path="data/creditcard.csv", session_id=str(uuid.uuid4()))
print(f"Finished in {time.time() - start:.2f} seconds.")
print(f"Total anomalies: {res.get('anomaly_count')}")
print(f"Status: {res.get('status')}")
