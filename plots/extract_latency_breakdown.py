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

# Conversion factor: nanoseconds to milliseconds
NANO_TO_MS = 1e-6

VALID_SCENARIOS = ['baseline', 'skew', 'scalability', 'network', 'packet_loss', 'sunflower', 'example']
VALID_WORKLOADS = ['ycsb', 'tpcc'] # TODO: Add your own benchmark to this list

def safe_mean_std(df, col):
    if len(df) == 0:
        return (np.nan, np.nan)
    return (
        round(df[col].mean(), 3),
        round(df[col].std(), 3)
    )

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
system_dirs = [system for system in system_dirs if '.' not in system]
summary_combined = pd.DataFrame(columns=['System', 'Avg Duration (ms)', 'Std Duration (ms)',
                                         'Avg Log Manager (ms)', 'Std Log Manager (ms)',
                                         'Avg Scheduler (ms)', 'Std Scheduler (ms)',
                                         'Avg Other (ms)', 'Std Other (ms)'])

for system in system_dirs:
    clients = [item for item in os.listdir(join(data_folder, system, "client")) if os.path.isdir(join(data_folder, system, "client", item))]
    txns_csvs = [join(data_folder, system, "client", client, "transactions.csv") for client in clients]
    events_csvs = [join(data_folder, system, "client", client, "txn_events.csv") for client in clients]
    # Merge the CSVs together
    txns_csv = pd.DataFrame(columns=["txn_id","coordinator","regions","partitions","generator","restarts","global_log_pos","sent_at","received_at"])
    events_csv = pd.DataFrame(columns=["txn_id","event","time","machine","home"])
    for i in range(len(clients)):
        cur_txns_csv = pd.read_csv(txns_csvs[i])
        txns_csv = pd.concat([txns_csv, cur_txns_csv], ignore_index=True)
        cur_events_csv = pd.read_csv(events_csvs[i])
        events_csv = pd.concat([events_csv, cur_events_csv], ignore_index=True)
    # Group events by txn_id for fast access
    event_groups = events_csv.groupby("txn_id")
    # Prepare list to collect results
    results = []
    txns_csv = txns_csv.tail(100) # For debugging purposes only, use the first 100 txns to speed up the script
    for _, txn in txns_csv.iterrows():
        txn_id = txn["txn_id"]
        sent_at = txn["sent_at"]
        received_at = txn["received_at"]
        duration_ms = (received_at - sent_at) * NANO_TO_MS
        is_mp = ';' in str(txn['partitions'])
        is_mh = ';' in str(txn['regions'])
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
            "Is MP": is_mp,
            "Is MH": is_mh,
            "Start time": sent_at,
            "End time": received_at,
            "Duration (ms)": round(duration_ms, 3),
            "Log manager (ms)": round(log_manager_ms, 3),
            "Scheduler (ms)": round(scheduler_ms, 3),
            "Other (ms)": round(other_ms, 3),
        })
    latency_breakdown_df = pd.DataFrame(results)
    os.makedirs(output_folder, exist_ok=True)
    latency_breakdown_df.to_csv(os.path.join(output_folder, f"latency_breakdown_{system}.csv"), index=False)
    # Define txn subcategories
    sp_sh_df = latency_breakdown_df[(~latency_breakdown_df["Is MP"]) & (~latency_breakdown_df["Is MH"])]
    mp_sh_df = latency_breakdown_df[(latency_breakdown_df["Is MP"]) & (~latency_breakdown_df["Is MH"])]
    mp_mh_df    = latency_breakdown_df[(latency_breakdown_df["Is MP"]) & (latency_breakdown_df["Is MH"])]
    # Compute base stats
    summary_stats = latency_breakdown_df[[
        "Duration (ms)",
        "Log manager (ms)",
        "Scheduler (ms)",
        "Other (ms)"
    ]].agg(['mean', 'std'])
    # Compute per-category stats
    sp_mean, sp_std = safe_mean_std(sp_sh_df, "Duration (ms)")
    mp_mean, mp_std = safe_mean_std(mp_sh_df, "Duration (ms)")
    mh_mean, mh_std = safe_mean_std(mp_mh_df, "Duration (ms)")
    # Flatten into one row
    summary_flat = pd.DataFrame([{
        "System": system,
        "Avg Duration (ms)": round(summary_stats.loc['mean', 'Duration (ms)'], 3),
        "Std Duration (ms)": round(summary_stats.loc['std', 'Duration (ms)'], 3),
        "Avg Log Manager (ms)": round(summary_stats.loc['mean', 'Log manager (ms)'], 3),
        "Std Log Manager (ms)": round(summary_stats.loc['std', 'Log manager (ms)'], 3),
        "Avg Scheduler (ms)": round(summary_stats.loc['mean', 'Scheduler (ms)'], 3),
        "Std Scheduler (ms)": round(summary_stats.loc['std', 'Scheduler (ms)'], 3),
        "Avg Other (ms)": round(summary_stats.loc['mean', 'Other (ms)'], 3),
        "Std Other (ms)": round(summary_stats.loc['std', 'Other (ms)'], 3),
        # Add per-category durations
        "Avg Duration (SP+SH)": sp_mean,
        "Std Duration (SP+SH)": sp_std,
        "Avg Duration (MP+SH)": mp_mean,
        "Std Duration (MP+SH)": mp_std,
        "Avg Duration (MH)": mh_mean,
        "Std Duration (MH)": mh_std,
    }])
    # Append row for system to the combined df
    summary_combined = pd.concat([summary_combined, summary_flat], ignore_index=True)

# Save summary
summary_combined.to_csv(os.path.join(output_folder, "latency_summary.csv"), index=False)

print("\nSummary statistics:")
print(summary_combined.round(3))

print("Done")