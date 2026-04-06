import time
import sys
import os
import uuid
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils import logger
import logging
logger.setLevel(logging.DEBUG)

def instrument_detection():
    # We will redefine process_and_detect but just add prints inside the script
    pass

import engines.detection as det

# We will just patch the detection.py locally with prints
with open("engines/detection.py", "r") as f:
    code = f.read()

code = code.replace("logger.info(\"Computing SHAP values for anomaly attribution...\")", "print('START SHAP', time.time()); logger.info('Computing SHAP values')")
code = code.replace("logger.info(\"SHAP attribution successfully embedded.\")", "print('END SHAP', time.time()); logger.info('SHAP embedded.')")
code = code.replace("if \"Class\" in pandas_df.columns:", "print('START THREAT', time.time()); if \"Class\" in pandas_df.columns:")
code = code.replace("df = df.with_columns(pl.Series(name=\"AI_Reason\"", "print('START AI REASON', time.time()); df = df.with_columns(pl.Series(name=\"AI_Reason\"")
code = code.replace("return {", "print('END DETECTION', time.time()); return {")

with open("engines/detection_instrumented.py", "w") as f:
    f.write(code)

start = time.time()
print("Starting process_and_detect...", start)
try:
    from engines.detection_instrumented import process_and_detect
    process_and_detect(file_path="data/creditcard.csv", session_id=str(uuid.uuid4()))
except Exception as e:
    print("Error:", e)
print("Finished completely in", time.time() - start)
