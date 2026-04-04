import pandas as pd
import numpy as np
import random

# 1. Set up the baseline normal data
n_rows = 5000
np.random.seed(42)

data = {
    "Transaction_ID": range(1, n_rows + 1),
    "User_Age": np.random.normal(35, 10, n_rows).astype(int), # Average age 35
    "Purchase_Amount": np.random.normal(80, 25, n_rows),      # Average spend $80
    "Session_Duration": np.random.normal(400, 150, n_rows),   # Average time 400 seconds
    "Location": np.random.choice(["Mumbai", "Thane", "Pune", "Delhi", "Bengaluru"], n_rows)
}

df = pd.DataFrame(data)

# Clean up baseline numbers to make them realistic
df["User_Age"] = df["User_Age"].clip(18, 75)
df["Purchase_Amount"] = df["Purchase_Amount"].clip(5, 300).round(2)
df["Session_Duration"] = df["Session_Duration"].clip(30, 1200).astype(int)

# 2. Inject 5% Hard Anomalies
n_anomalies = int(n_rows * 0.05)
anomaly_indices = random.sample(range(n_rows), n_anomalies)

for idx in anomaly_indices:
    anomaly_type = random.choice(["high_amount", "negative_age", "fraud_behavior", "typo"])
    
    if anomaly_type == "high_amount":
        df.loc[idx, "Purchase_Amount"] = np.random.uniform(2000, 10000)
    elif anomaly_type == "negative_age":
        df.loc[idx, "User_Age"] = np.random.uniform(-50, -1)
    elif anomaly_type == "fraud_behavior":
        # Huge amount, almost 0 session time
        df.loc[idx, "Purchase_Amount"] = np.random.uniform(1000, 5000)
        df.loc[idx, "Session_Duration"] = np.random.uniform(1, 5)
    elif anomaly_type == "typo":
        df.loc[idx, "Location"] = random.choice(["Mumbay", "Delhy", "Punee", "UNKNOWN"])

# 3. Inject Missing Values (NaNs) into 2% of the data
nan_indices = random.sample(range(n_rows), int(n_rows * 0.02))
for idx in nan_indices:
    col_to_blank = random.choice(["User_Age", "Purchase_Amount", "Session_Duration"])
    df.loc[idx, col_to_blank] = np.nan

# Save to CSV
file_name = "synthetic_ecommerce_data.csv"
df.to_csv(file_name, index=False)
print(f"✅ Generated {file_name} with {n_rows} rows and realistic anomalies!")