import os
from os.path import join, isdir
import numpy as np
import pandas as pd
import argparse
import re
from datetime import datetime
import json

import latency_breakdown

'''
Script for decomposing the transactional latency into individual components.
'''

VALID_SCENARIOS = ['baseline', 'skew', 'scalability', 'network', 'packet_loss', 'sunflower', 'example']
VALID_WORKLOADS = ['ycsb', 'tpcc'] # TODO: Add your own benchmark to this list
LATENCY_PERCENTILES = [50,95,99]
VALID_ENVIRONMENTS = ['local', 'st', 'aws']

# Argument parser
parser = argparse.ArgumentParser(description="Decompose the latency of transactions into components and plot graph stacked bar chart.")
parser.add_argument('-df', '--data_folder', default='plots/raw_data/ycsb/lat_breakdown', help='Path to folder with raw data')
parser.add_argument('-w',  '--workload', default='ycsb', choices=VALID_WORKLOADS, help='Workload evaluated (default: ycsb)')
parser.add_argument('-o',  '--output_folder', default='plots/data/final/ycsb/latency_breakdown', help='Folder where to store the processed data')

args = parser.parse_args()
data_folder = args.data_folder
workload = args.workload
output_folder = args.output_folder

system_dirs = os.listdir(data_folder)

# Hard-coded TODO: make loop for all systems
system = system_dirs[0]
txns_csv = pd.read_csv(join(data_folder, system, "transactions.csv"))
events_csv = pd.read_csv(join(data_folder, system, "txn_events.csv"))



# Conversion factor: nanoseconds to milliseconds
NANO_TO_MS = 1e-6

# Group events by txn_id for fast access
event_groups = events_csv.groupby("txn_id")

# Prepare list to collect results
results = []

for _, txn in txns_csv.iterrows():
    txn_id = txn["txn_id"]
    sent_at = txn["sent_at"]
    received_at = txn["received_at"]
    duration_ms = (received_at - sent_at) * NANO_TO_MS

    log_manager_ms = 0
    scheduler_ms = 0

    # Get event rows for this txn, if any
    if txn_id in event_groups.groups:
        txn_events = event_groups.get_group(txn_id)

        # Log Manager: EXIT_LOG_MANAGER - ENTER_LOG_MANAGER_IN_BATCH
        try:
            enter_log = txn_events[txn_events["event"] == "ENTER_LOG_MANAGER_IN_BATCH"]["time"].min()
            exit_log = txn_events[txn_events["event"] == "EXIT_LOG_MANAGER"]["time"].max()
            if pd.notna(enter_log) and pd.notna(exit_log):
                log_manager_ms = (exit_log - enter_log) * NANO_TO_MS
        except Exception:
            pass

        # Scheduler: DISPATCHED_SLOW - ENTER_SCHEDULER
        try:
            enter_sched = txn_events[txn_events["event"] == "ENTER_SCHEDULER"]["time"].min()
            dispatched = txn_events[txn_events["event"] == "DISPATCHED_SLOW"]["time"].max()
            if pd.notna(enter_sched) and pd.notna(dispatched):
                scheduler_ms = (dispatched - enter_sched) * NANO_TO_MS
        except Exception:
            pass

    other_ms = max(0, duration_ms - log_manager_ms - scheduler_ms)

    results.append({
        "Txn_ID": txn_id,
        "Start time": sent_at,
        "End time": received_at,
        "Duration (ms)": round(duration_ms, 3),
        "Log manager (ms)": round(log_manager_ms, 3),
        "Scheduler (ms)": round(scheduler_ms, 3),
        "Other (ms)": round(other_ms, 3),
    })

# Final DataFrame
latency_breakdown_df = pd.DataFrame(results)
os.makedirs(output_folder, exist_ok=True)
latency_breakdown_df.to_csv(os.path.join(output_folder, "latency_breakdown.csv"), index=False)

print(latency_breakdown_df.head())

# Compute averages and standard deviations
summary_stats = latency_breakdown_df[[
    "Duration (ms)",
    "Log manager (ms)",
    "Scheduler (ms)",
    "Other (ms)"
]].agg(['mean', 'std'])

# Flatten into one row
summary_combined = pd.DataFrame([{
    "Avg Duration (ms)": round(summary_stats.loc['mean', 'Duration (ms)'], 3),
    "Std Duration (ms)": round(summary_stats.loc['std', 'Duration (ms)'], 3),
    "Avg Log Manager (ms)": round(summary_stats.loc['mean', 'Log manager (ms)'], 3),
    "Std Log Manager (ms)": round(summary_stats.loc['std', 'Log manager (ms)'], 3),
    "Avg Scheduler (ms)": round(summary_stats.loc['mean', 'Scheduler (ms)'], 3),
    "Std Scheduler (ms)": round(summary_stats.loc['std', 'Scheduler (ms)'], 3),
    "Avg Other (ms)": round(summary_stats.loc['mean', 'Other (ms)'], 3),
    "Std Other (ms)": round(summary_stats.loc['std', 'Other (ms)'], 3),
}])

summary_combined['System'] = system_dirs
summary_combined = summary_combined.iloc[:, [8,0,1,2,3,4,5,6,7]] 

# Save summary
summary_combined.to_csv(os.path.join(output_folder, "latency_summary.csv"), index=False)

print("\nSummary statistics:")
print(summary_combined.round(3))

print("Done")