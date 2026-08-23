import pandas as pd
import json

df = pd.read_csv('results/experiment_1_raw.csv')
records = df.to_dict(orient='records')
with open('raw_results_clean.json', 'w') as f:
    json.dump(records, f, indent=2)
