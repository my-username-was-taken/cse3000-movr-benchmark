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

def extract_component_times(cur_events):
    server_ms = 0.0
    forwarder_ms = 0.0
    log_manager_ms = 0.0
    scheduler_ms = 0.0
    worker_ms = 0.0
    idle_ms = 0.0
    # Track when stages are entered
    server_enter_time = None
    forwarder_enter_time = None
    log_enter_time = None
    sched_enter_time = None
    worker_enter_time = None
    idle_enter_time = None
    for _, event_row in cur_events.iterrows():
        event = event_row["event"]
        time = event_row["time"]
        # === Server ===
        if event == "ENTER_SERVER" or event == "RETURN_TO_SERVER":
            server_enter_time = time
        elif (event == "EXIT_SERVER_TO_FORWARDER" or event == "EXIT_SERVER_TO_CLIENT") and server_enter_time is not None:
            server_ms += (time - server_enter_time) * NANO_TO_MS
            server_enter_time = None
        # === Forwarder ===
        if event == "ENTER_FORWARDER":
            forwarder_enter_time = time
        elif (event == "EXIT_FORWARDER_TO_SEQUENCER" or event == "EXIT_FORWARDER_TO_MULTI_HOME_ORDERER") and forwarder_enter_time is not None:
            forwarder_ms += (time - forwarder_enter_time) * NANO_TO_MS
            forwarder_enter_time = None
        # === Log Manager ===
        if event == "ENTER_LOG_MANAGER_IN_BATCH":
            log_enter_time = time
        elif event == "EXIT_LOG_MANAGER" and log_enter_time is not None:
            log_manager_ms += (time - log_enter_time) * NANO_TO_MS
            log_enter_time = None
        # === Scheduler ===
        elif event == "ENTER_SCHEDULER":
            sched_enter_time = time
        elif event == "DISPATCHED_SLOW" and sched_enter_time is not None:
            scheduler_ms += (time - sched_enter_time) * NANO_TO_MS
            sched_enter_time = None
        # === Worker ===
        elif event == "ENTER_WORKER":
            worker_enter_time = time
        elif event == "EXIT_WORKER" and worker_enter_time is not None:
            worker_ms += (time - worker_enter_time) * NANO_TO_MS
            worker_enter_time = None
        # === Idle ===
        elif event == "EXIT_SERVER_TO_FORWARDER":
            idle_enter_time = time
        elif event == "ENTER_WORKER" and idle_enter_time is not None:
            idle_ms += (time - idle_enter_time) * NANO_TO_MS
            idle_enter_time = None
    return server_ms, log_manager_ms, scheduler_ms, worker_ms, idle_ms

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
            txn_events = event_groups.get_group(txn_id).sort_values("time")
            server_ms, log_manager_ms, scheduler_ms, worker_ms, idle_ms = extract_component_times(txn_events)
        results.append({
            "Txn_ID": txn_id,
            "Is MP": is_mp,
            "Is MH": is_mh,
            "Start time": sent_at,
            "End time": received_at,
            "Duration (ms)": round(duration_ms, 3),
            "Server (ms)": round(server_ms, 3),
            "Log manager (ms)": round(log_manager_ms, 3),
            "Scheduler (ms)": round(scheduler_ms, 3),
            "Worker (ms)": round(worker_ms, 3),
            "Idle (ms)": round(idle_ms, 3),
            "Other (ms)": round(max(0, duration_ms - log_manager_ms - scheduler_ms - worker_ms), 3),
        })
    latency_breakdown_df = pd.DataFrame(results)
    os.makedirs(output_folder, exist_ok=True)
    latency_breakdown_df.to_csv(os.path.join(output_folder, f"latency_breakdown_{system}.csv"), index=False)
    # Define txn subcategories
    sp_sh_df = latency_breakdown_df[(~latency_breakdown_df["Is MP"]) & (~latency_breakdown_df["Is MH"])]
    mp_sh_df = latency_breakdown_df[(latency_breakdown_df["Is MP"]) & (~latency_breakdown_df["Is MH"])]
    mp_mh_df = latency_breakdown_df[(latency_breakdown_df["Is MP"]) & (latency_breakdown_df["Is MH"])]
    # Compute base stats
    summary_stats_all = latency_breakdown_df[[
        "Duration (ms)",
        "Server (ms)",
        "Log manager (ms)",
        "Scheduler (ms)",
        "Worker (ms)",
        "Idle (ms)",
        "Other (ms)"
    ]].agg(['mean', 'std'])
    summary_stats_sp_sh = sp_sh_df[[
        "Duration (ms)",
        "Server (ms)",
        "Log manager (ms)",
        "Scheduler (ms)",
        "Worker (ms)",
        "Idle (ms)",
        "Other (ms)"
    ]].agg(['mean', 'std'])
    summary_stats_mp_sh = mp_sh_df[[
        "Duration (ms)",
        "Server (ms)",
        "Log manager (ms)",
        "Scheduler (ms)",
        "Worker (ms)",
        "Idle (ms)",
        "Other (ms)"
    ]].agg(['mean', 'std'])
    summary_stats_mp_mh = mp_mh_df[[
        "Duration (ms)",
        "Server (ms)",
        "Log manager (ms)",
        "Scheduler (ms)",
        "Worker (ms)",
        "Idle (ms)",
        "Other (ms)"
    ]].agg(['mean', 'std'])

    # Flatten into one row
    summary_flat = pd.DataFrame([{
        "System": system,
        # All Txns
        "Avg Duration (ms)": round(summary_stats_all.loc['mean', 'Duration (ms)'], 3),
        "Std Duration (ms)": round(summary_stats_all.loc['std', 'Duration (ms)'], 3), 
        "Avg Server (ms)": round(summary_stats_all.loc['mean', 'Server (ms)'], 3),
        "Std Server (ms)": round(summary_stats_all.loc['std', 'Server (ms)'], 3),
        "Server (%)": round(summary_stats_all.loc['mean', 'Server (ms)'] / summary_stats_all.loc['mean', 'Duration (ms)'], 3),
        "Avg Log Manager (ms)": round(summary_stats_all.loc['mean', 'Log manager (ms)'], 3),
        "Std Log Manager (ms)": round(summary_stats_all.loc['std', 'Log manager (ms)'], 3),
        "Log Manager (%)": round(summary_stats_all.loc['mean', 'Log manager (ms)'] / summary_stats_all.loc['mean', 'Duration (ms)'], 3),
        "Avg Scheduler (ms)": round(summary_stats_all.loc['mean', 'Scheduler (ms)'], 3),
        "Std Scheduler (ms)": round(summary_stats_all.loc['std', 'Scheduler (ms)'], 3),
        "Scheduler (%)": round(summary_stats_all.loc['mean', 'Scheduler (ms)'] / summary_stats_all.loc['mean', 'Duration (ms)'], 3),
        "Avg Worker (ms)": round(summary_stats_all.loc['mean', 'Worker (ms)'], 3),
        "Std Worker (ms)": round(summary_stats_all.loc['std', 'Worker (ms)'], 3),
        "Worker (%)": round(summary_stats_all.loc['mean', 'Worker (ms)'] / summary_stats_all.loc['mean', 'Duration (ms)'], 3),
        "Avg Idle (ms)": round(summary_stats_all.loc['mean', 'Idle (ms)'], 3),
        "Std Idle (ms)": round(summary_stats_all.loc['std', 'Idle (ms)'], 3),
        "Idle (%)": round(summary_stats_all.loc['mean', 'Idle (ms)'] / summary_stats_all.loc['mean', 'Duration (ms)'], 3),
        "Avg Other (ms)": round(summary_stats_all.loc['mean', 'Other (ms)'], 3),
        "Std Other (ms)": round(summary_stats_all.loc['std', 'Other (ms)'], 3),
        "Other (%)": round(summary_stats_all.loc['mean', 'Other (ms)'] / summary_stats_all.loc['mean', 'Duration (ms)'], 3),
        # SP SH Txns
        "SP_SH Avg Duration (ms)": round(summary_stats_sp_sh.loc['mean', 'Duration (ms)'], 3),
        "SP_SH Std Duration (ms)": round(summary_stats_sp_sh.loc['std', 'Duration (ms)'], 3),
        "SP_SH Avg Server (ms)": round(summary_stats_sp_sh.loc['mean', 'Server (ms)'], 3),
        "SP_SH Std Server (ms)": round(summary_stats_sp_sh.loc['std', 'Server (ms)'], 3),
        "SP_SH Server (%)": round(summary_stats_sp_sh.loc['mean', 'Server (ms)'] / summary_stats_sp_sh.loc['mean', 'Duration (ms)'], 3),
        "SP_SH Avg Log Manager (ms)": round(summary_stats_sp_sh.loc['mean', 'Log manager (ms)'], 3),
        "SP_SH Std Log Manager (ms)": round(summary_stats_sp_sh.loc['std', 'Log manager (ms)'], 3),
        "SP_SH Log Manager (%)": round(summary_stats_sp_sh.loc['mean', 'Log manager (ms)'] / summary_stats_sp_sh.loc['mean', 'Duration (ms)'], 3),
        "SP_SH Avg Scheduler (ms)": round(summary_stats_sp_sh.loc['mean', 'Scheduler (ms)'], 3),
        "SP_SH Std Scheduler (ms)": round(summary_stats_sp_sh.loc['std', 'Scheduler (ms)'], 3),
        "SP_SH Scheduler (%)": round(summary_stats_sp_sh.loc['mean', 'Scheduler (ms)'] / summary_stats_sp_sh.loc['mean', 'Duration (ms)'], 3),
        "SP_SH Avg Worker (ms)": round(summary_stats_sp_sh.loc['mean', 'Worker (ms)'], 3),
        "SP_SH Std Worker (ms)": round(summary_stats_sp_sh.loc['std', 'Worker (ms)'], 3),
        "SP_SH Worker (%)": round(summary_stats_sp_sh.loc['mean', 'Worker (ms)'] / summary_stats_sp_sh.loc['mean', 'Duration (ms)'], 3),
        "SP_SH Avg Idle (ms)": round(summary_stats_sp_sh.loc['mean', 'Idle (ms)'], 3),
        "SP_SH Std Idle (ms)": round(summary_stats_sp_sh.loc['std', 'Idle (ms)'], 3),
        "SP_SH Idle (%)": round(summary_stats_sp_sh.loc['mean', 'Idle (ms)'] / summary_stats_sp_sh.loc['mean', 'Duration (ms)'], 3),
        "SP_SH Avg Other (ms)": round(summary_stats_sp_sh.loc['mean', 'Other (ms)'], 3),
        "SP_SH Std Other (ms)": round(summary_stats_sp_sh.loc['std', 'Other (ms)'], 3),
        "SP_SH Other (%)": round(summary_stats_sp_sh.loc['mean', 'Other (ms)'] / summary_stats_sp_sh.loc['mean', 'Duration (ms)'], 3),
        # MP SH Txns
        "MP_SH Avg Duration (ms)": round(summary_stats_mp_sh.loc['mean', 'Duration (ms)'], 3),
        "MP_SH Std Duration (ms)": round(summary_stats_mp_sh.loc['std', 'Duration (ms)'], 3),
        "MP_SH Avg Server (ms)": round(summary_stats_mp_sh.loc['mean', 'Server (ms)'], 3),
        "MP_SH Std Server (ms)": round(summary_stats_mp_sh.loc['std', 'Server (ms)'], 3),
        "MP_SH Server (%)": round(summary_stats_mp_sh.loc['mean', 'Server (ms)'] / summary_stats_mp_sh.loc['mean', 'Duration (ms)'], 3),
        "MP_SH Avg Log Manager (ms)": round(summary_stats_mp_sh.loc['mean', 'Log manager (ms)'], 3),
        "MP_SH Std Log Manager (ms)": round(summary_stats_mp_sh.loc['std', 'Log manager (ms)'], 3),
        "MP_SH Log Manager (%)": round(summary_stats_mp_sh.loc['mean', 'Log manager (ms)'] / summary_stats_mp_sh.loc['mean', 'Duration (ms)'], 3),
        "MP_SH Avg Scheduler (ms)": round(summary_stats_mp_sh.loc['mean', 'Scheduler (ms)'], 3),
        "MP_SH Std Scheduler (ms)": round(summary_stats_mp_sh.loc['std', 'Scheduler (ms)'], 3),
        "MP_SH Scheduler (%)": round(summary_stats_mp_sh.loc['mean', 'Scheduler (ms)'] / summary_stats_mp_sh.loc['mean', 'Duration (ms)'], 3),
        "MP_SH Avg Worker (ms)": round(summary_stats_mp_sh.loc['mean', 'Worker (ms)'], 3),
        "MP_SH Std Worker (ms)": round(summary_stats_mp_sh.loc['std', 'Worker (ms)'], 3),
        "MP_SH Worker (%)": round(summary_stats_mp_sh.loc['mean', 'Worker (ms)'] / summary_stats_mp_sh.loc['mean', 'Duration (ms)'], 3),
        "MP_SH Avg Idle (ms)": round(summary_stats_mp_sh.loc['mean', 'Idle (ms)'], 3),
        "MP_SH Std Idle (ms)": round(summary_stats_mp_sh.loc['std', 'Idle (ms)'], 3),
        "MP_SH Idle (%)": round(summary_stats_mp_sh.loc['mean', 'Idle (ms)'] / summary_stats_mp_sh.loc['mean', 'Duration (ms)'], 3),
        "MP_SH Avg Other (ms)": round(summary_stats_mp_sh.loc['mean', 'Other (ms)'], 3),
        "MP_SH Std Other (ms)": round(summary_stats_mp_sh.loc['std', 'Other (ms)'], 3),
        "MP_SH Other (%)": round(summary_stats_mp_sh.loc['mean', 'Other (ms)'] / summary_stats_mp_sh.loc['mean', 'Duration (ms)'], 3),
        # MP MH Txns
        "MP_MH Avg Duration (ms)": round(summary_stats_mp_mh.loc['mean', 'Duration (ms)'], 3),
        "MP_MH Std Duration (ms)": round(summary_stats_mp_mh.loc['std', 'Duration (ms)'], 3),
        "MP_MH Avg Server (ms)": round(summary_stats_mp_mh.loc['mean', 'Server (ms)'], 3),
        "MP_MH Std Server (ms)": round(summary_stats_mp_mh.loc['std', 'Server (ms)'], 3),
        "MP_MH Server (%)": round(summary_stats_mp_mh.loc['mean', 'Server (ms)'] / summary_stats_mp_mh.loc['mean', 'Duration (ms)'], 3),
        "MP_MH Avg Log Manager (ms)": round(summary_stats_mp_mh.loc['mean', 'Log manager (ms)'], 3),
        "MP_MH Std Log Manager (ms)": round(summary_stats_mp_mh.loc['std', 'Log manager (ms)'], 3),
        "MP_MH Log Manager (%)": round(summary_stats_mp_mh.loc['mean', 'Log manager (ms)'] / summary_stats_mp_mh.loc['mean', 'Duration (ms)'], 3),
        "MP_MH Avg Scheduler (ms)": round(summary_stats_mp_mh.loc['mean', 'Scheduler (ms)'], 3),
        "MP_MH Std Scheduler (ms)": round(summary_stats_mp_mh.loc['std', 'Scheduler (ms)'], 3),
        "MP_MH Scheduler (%)": round(summary_stats_mp_mh.loc['mean', 'Scheduler (ms)'] / summary_stats_mp_mh.loc['mean', 'Duration (ms)'], 3),
        "MP_MH Avg Worker (ms)": round(summary_stats_mp_mh.loc['mean', 'Worker (ms)'], 3),
        "MP_MH Std Worker (ms)": round(summary_stats_mp_mh.loc['std', 'Worker (ms)'], 3),
        "MP_MH Worker (%)": round(summary_stats_mp_mh.loc['mean', 'Worker (ms)'] / summary_stats_mp_mh.loc['mean', 'Duration (ms)'], 3),
        "MP_MH Avg Idle (ms)": round(summary_stats_mp_mh.loc['mean', 'Idle (ms)'], 3),
        "MP_MH Std Idle (ms)": round(summary_stats_mp_mh.loc['std', 'Idle (ms)'], 3),
        "MP_MH Idle (%)": round(summary_stats_mp_mh.loc['mean', 'Idle (ms)'] / summary_stats_mp_mh.loc['mean', 'Duration (ms)'], 3),
        "MP_MH Avg Other (ms)": round(summary_stats_mp_mh.loc['mean', 'Other (ms)'], 3),
        "MP_MH Std Other (ms)": round(summary_stats_mp_mh.loc['std', 'Other (ms)'], 3),
        "MP_MH Other (%)": round(summary_stats_mp_mh.loc['mean', 'Other (ms)'] / summary_stats_mp_mh.loc['mean', 'Duration (ms)'], 3),
    }])
    # Append row for current system to the combined DataFrame
    summary_combined = pd.concat([summary_combined, summary_flat], ignore_index=True)

# Save summary
summary_combined.to_csv(os.path.join(output_folder, "latency_summary.csv"), index=False)

print("\nSummary statistics:")
print(summary_combined.round(3))

print("Done")