import os
from os.path import join, isdir
import numpy as np
import pandas as pd
import argparse
import re
from datetime import datetime

import eval_systems

'''
Script for extracting the final results out of the logs and CSVs created during the experiment runs.
Intended to be run on own PC, just before the actual plotting of the results.
The script will populate the CSVs in 'plots/data' and generate a graph in 'plots/output'.
'''

VALID_SCENARIOS = ['baseline', 'skew', 'scalability', 'network', 'packet_loss', 'sunflower', 'example']
VALID_WORKLOADS = ['ycsbt', 'tpcc'] # TODO: Add your own benchmark to this list
VALID_ENVIRONMENTS = ['local', 'st', 'aws']

# Argument parser
parser = argparse.ArgumentParser(description="Extract experiment results and plot graph for a given scenario.")
parser.add_argument('-s', '--scenario', default='network', choices=VALID_SCENARIOS, help='Type of experiment scenario to analyze (default: baseline)')
parser.add_argument('-w', '--workload', default='ycsbt', choices=VALID_WORKLOADS, help='Workload to run (default: ycsbt)')
parser.add_argument('-e', '--environment', default='st', choices=VALID_ENVIRONMENTS, help='What type of machine the experiment was run on.')

args = parser.parse_args()
scenario = args.scenario
workload = args.workload
env = args.environment

print(f"Extracting data for scenario: '{scenario}' and workload: '{workload}'")

# Define paths

BASE_DIR_PATH = join("plots/raw_data", workload, scenario)
#CLIENT_DATA_DIR = join(BASE_DIR_PATH, "client")
#LOG_DIR = join(BASE_DIR_PATH, "raw_logs")

out_csv = f'{scenario}.csv'
OUT_CSV_PATH = join("plots/data/final", workload, out_csv)
SYSTEMS_LIST = ['Calvin', 'SLOG', 'Detock', 'Caerus', 'Mencius']
METRICS_LIST = ['throughput', 'p50', 'p90', 'p95', 'p99', 'aborts', 'bytes', 'cost']

MAX_YCSBT_HOT_RECORDS = 250.0 # Check whether this needs to be adjusted per current exp setup

# Constants for the hourly cost of deploying all the servers on m4.2xlarge VMs (each region has 4 VMs). Price as of 28.3.25
#              euw1  euw2  usw1  usw2  use1  use2  apne1 apne2
vm_cost = 4 * (0.444+0.464+0.468+0.400+0.400+0.400+0.516+0.492)
# The cost of transferring 1GB of data out from the source region (the row). Price as of 28.3.25
if env == 'local' or env == 'st':
    data_transfer_cost_matrix = [ # Here we just pretend that we have data transfer costs and make them uniform for all source, destination pairs
        [0,0.02], # 131.180.125.57
        [0.02,0]  # 131.180.125.40
        # [0,0.02,0.02,0.02,0.02,0.02,0.02,0.02], # euw1
        # [0.02,0,0.02,0.02,0.02,0.02,0.02,0.02], # euw2
        # [0.02,0.02,0,0.02,0.02,0.02,0.02,0.02], # usw1
        # [0.02,0.02,0.02,0,0.02,0.02,0.02,0.02], # usw2
        # [0.02,0.02,0.02,0.02,0,0.02,0.02,0.02], # use1
        # [0.02,0.02,0.02,0.02,0.02,0,0.02,0.02], # use2
        # [0.02,0.02,0.02,0.02,0.02,0.02,0,0.02], # apne1
        # [0.02,0.02,0.02,0.02,0.02,0.02,0.02,0]  # apne2
    ]
elif env == 'aws':
    data_transfer_cost_matrix = [
        [0,0.02,0.02,0.02,0.02,0.02,0.02,0.02], # euw1
        [0.02,0,0.02,0.02,0.02,0.02,0.02,0.02], # euw2
        [0.02,0.02,0,0.02,0.02,0.02,0.02,0.02], # usw1
        [0.02,0.02,0.02,0,0.02,0.02,0.02,0.02], # usw2
        [0.02,0.02,0.02,0.02,0,0.01,0.02,0.02], # use1
        [0.02,0.02,0.02,0.02,0.01,0,0.02,0.02], # use2
        [0.09,0.09,0.09,0.09,0.09,0.09,0,0.09], # apne1
        [0.08,0.08,0.08,0.08,0.08,0.08,0.08,0]  # apne2
    ]

def extract_timestamp(timestamp_str):
    # Extract timestamp: I0430 10:14:36.795380
    ts_str = re.search(r"I\d{4} (\d{2}:\d{2}:\d{2}\.\d+)", line).group(1)
    # Extract date part: 0430 (MMDD)
    date_part = re.search(r"I(\d{4})", line).group(1)
    month, day = int(date_part[:2]), int(date_part[2:])
    # Convert to full datetime
    now = datetime.now()
    ts = datetime(now.year, month, day, *map(int, ts_str.split(":")[:2]), int(float(ts_str.split(":")[2])))
    return int(ts.timestamp() * 1000)

def summarize_bytes_sent(df, start_ts, end_ts):
    """
    Summarize total bytes sent to each destination between two timestamps.
    
    :param data: Loaded raw CSV data as a Pandas dataframe.
    :param start_ts: Start timestamp (ms since epoch).
    :param end_ts: End timestamp (ms since epoch).
    :return: A pandas DataFrame with destinations and total bytes sent.
    """
    # Filter rows within the timestamp range
    df_filtered = df[(df["Time"] >= start_ts) & (df["Time"] <= end_ts)]
    # TODO: Fix this, the reported values are actually cumulative
    # Group by destination and sum the bytes sent
    summary = df_filtered.groupby("To")["FromBytes"].sum().reset_index()
    # Sort by total bytes descending
    summary = summary.sort_values(by="FromBytes", ascending=False)
    return summary

def get_server_ips_from_conf(conf):
    return []

# Load log files into strings
log_files = {}
tags = {}
throughputs = {}
start_timestamps = {}
end_timestamps = {}
system_dirs = [join(BASE_DIR_PATH, dir) for dir in os.listdir(BASE_DIR_PATH) if isdir(join(BASE_DIR_PATH, dir))]
for system in system_dirs:
    log_files[system.split('/')[-1]] = {}
    tags[system.split('/')[-1]] = {}
    throughputs[system.split('/')[-1]] = {}
    start_timestamps[system.split('/')[-1]] = {}
    end_timestamps[system.split('/')[-1]] = {}
    x_vals = [join(system, dir) for dir in os.listdir(system)]
    for x_val in x_vals:
        log_files[system.split('/')[-1]][x_val.split('/')[-1]] = {}
        with open(join(x_val, 'raw_logs', 'benchmark_cmd.log'), "r", encoding="utf-8") as f:
            log_files[system.split('/')[-1]][x_val.split('/')[-1]]['benchmark_cmd'] = f.read().split('\n')
        with open(join(x_val, 'raw_logs', 'benchmark_container.log'), "r", encoding="utf-8") as f:
            log_files[system.split('/')[-1]][x_val.split('/')[-1]]['benchmark_container'] = f.read().split('\n')
        log_files = os.listdir(join(x_val, 'raw_logs'))
        # Get the '.conf' file (for getting all the IPs involved)
        for file in log_files:
            if '.conf' in file:
                with open(join(x_val, 'raw_logs', file), "r", encoding="utf-8") as f:
                    log_files[system.split('/')[-1]][x_val.split('/')[-1]]['conf_file'] = f.read().split('\n')
        server_ips = get_server_ips_from_conf(log_files[system.split('/')[-1]][x_val.split('/')[-1]]['conf_file'])
        net_traffic_log_files = [f'net_traffic_{ip.replace()}.csv' for ip in server_ips]
        # Load all the network traffic data
        log_files[system.split('/')[-1]][x_val.split('/')[-1]]['net_traffic_logs'] = {}
        for ip in server_ips:
            pass # TODO: Continue here
        # Extract tag name from cmd log
        for line in log_files[system.split('/')[-1]][x_val.split('/')[-1]]['benchmark_cmd']:
            if 'admin INFO: Tag: ' in line:
                tag = line.split('admin INFO: Tag: ')[1]
        tags[system.split('/')[-1]][x_val.split('/')[-1]] = tag
        # Extract throughput from container log
        for line in log_files[system.split('/')[-1]][x_val.split('/')[-1]]['benchmark_container']:
            if 'Avg. TPS: ' in line:
                throughputs[system.split('/')[-1]][x_val.split('/')[-1]] = int(line.split('Avg. TPS: ')[1])
            # Get the timestamp between the actual start and end of the experiment
            elif 'Start sending transactions with' in line:
                start_timestamps[system.split('/')[-1]][x_val.split('/')[-1]] = extract_timestamp(line)
            elif 'Results were written to' in line:
                end_timestamps[system.split('/')[-1]][x_val.split('/')[-1]] = extract_timestamp(line)
print(f"All log files loaded")

# Load CSV files into pandas DataFrames
csv_files = {}
for system in system_dirs:
    csv_files[system.split('/')[-1]] = {}
    x_vals = [join(system, dir) for dir in os.listdir(system)]
    for x_val in x_vals:
        csv_files[system.split('/')[-1]][x_val.split('/')[-1]] = {}
        clients = [join(x_val, 'client', obj) for obj in os.listdir(join(x_val, 'client')) if isdir(join(x_val, 'client', obj))]
        for client in clients:
            csv_files[system.split('/')[-1]][x_val.split('/')[-1]][client.split('/')[-1]] = {}
            # Read in all 4 extected files
            csv_files[system.split('/')[-1]][x_val.split('/')[-1]][client.split('/')[-1]]['metadata'] = pd.read_csv(join(client, 'metadata.csv'))
            csv_files[system.split('/')[-1]][x_val.split('/')[-1]][client.split('/')[-1]]['summary'] = pd.read_csv(join(client, 'summary.csv'))
            csv_files[system.split('/')[-1]][x_val.split('/')[-1]][client.split('/')[-1]]['transactions'] = pd.read_csv(join(client, 'transactions.csv'))
            csv_files[system.split('/')[-1]][x_val.split('/')[-1]][client.split('/')[-1]]['txn_events'] = pd.read_csv(join(client, 'txn_events.csv'))
            #if 'iftop_eg.csv' in os.listdir(client):
            #    csv_files[system.split('/')[-1]][x_val.split('/')[-1]][client.split('/')[-1]]['byte_transfers'] = pd.read_csv(join(client, 'iftop_eg.csv'))
            #if 'net_traffic.csv' in os.listdir(client):
            #    csv_files[system.split('/')[-1]][x_val.split('/')[-1]][client.split('/')[-1]]['byte_transfers'] = pd.read_csv(join(client, 'net_traffic.csv'))
print("All CSV files loaded")

# Get the latencies (p50, p90, p95, p99)
percentiles = [50, 90, 95, 99]
latencies = {}
for system in system_dirs:
    latencies[system.split('/')[-1]] = {}
    x_vals = [join(system, dir) for dir in os.listdir(system)]
    for x_val in x_vals:
        all_latencies = []
        clients = [obj for obj in os.listdir(join(x_val, 'client')) if isdir(join(x_val, 'client', obj))]
        for client in clients:
            client_txns = csv_files[system.split('/')[-1]][x_val.split('/')[-1]][client]['transactions']
            client_txns["duration"] = client_txns["received_at"] - client_txns["sent_at"]
            all_latencies.extend(list(client_txns["duration"]))
        latency_percentiles = {f"p{p}": np.percentile(np.array(all_latencies) / 1000000, p) for p in percentiles}
        latencies[system.split('/')[-1]][x_val.split('/')[-1]] = latency_percentiles
print("All latencies extracted")

# Get the abort rate
abort_rates = {}
for system in system_dirs:
    abort_rates[system.split('/')[-1]] = {}
    x_vals = [join(system, dir) for dir in os.listdir(system)]
    for x_val in x_vals:
        total_txns = 0
        total_aborts = 0
        clients = [obj for obj in os.listdir(join(x_val, 'client')) if isdir(join(x_val, 'client', obj))]
        for client in clients:
            total_txns += csv_files[system.split('/')[-1]][x_val.split('/')[-1]][client]['summary']['single_partition'].iloc[0]
            total_txns += csv_files[system.split('/')[-1]][x_val.split('/')[-1]][client]['summary']['multi_partition'].iloc[0]
            total_aborts += csv_files[system.split('/')[-1]][x_val.split('/')[-1]][client]['summary']['aborted'].iloc[0]
        abort_rates[system.split('/')[-1]][x_val.split('/')[-1]] = 100 * total_aborts / total_txns

# Get the byte transfers
# Here we will need to consider the duration of the experiemnt
# TODO: Figure out how to make an extrapolation that is an objective estimate (because of start & end anomalies)
byte_transfers = {}
total_costs = {}
for system in system_dirs:
    byte_transfers[system.split('/')[-1]] = {}
    total_costs[system.split('/')[-1]] = {}
    x_vals = [join(system, dir) for dir in os.listdir(system)]
    for x_val in x_vals:
        start = start_timestamps[system.split('/')[-1]][x_val.split('/')[-1]]
        end = end_timestamps[system.split('/')[-1]][x_val.split('/')[-1]]
        # TODO: Actually read real data from a file here
        if env == 'local' or env == 'st':
            no_clients = len(csv_files[system.split('/')[-1]][x_val.split('/')[-1]].keys())
            bytes_transfered_matrix = [ # The hard-coded values if we don't have real data, otherwise overwite this below
                [0, 1], # 131.180.125.57
                [1, 0]  # 131.180.125.40
                # [111,112,113,114,115,116,117,118], # euw1
                # [211,212,213,214,215,216,217,218], # euw2
                # [311,312,313,314,315,316,317,318], # usw1
                # [411,412,413,414,415,416,417,418], # usw2
                # [511,512,513,514,515,516,517,518], # use1
                # [611,612,613,614,615,616,617,618], # use2
                # [711,712,713,714,715,716,717,718], # apne1
                # [811,812,813,814,815,816,817,818]  # apne2
            ]
            for i, client in enumerate(csv_files[system.split('/')[-1]][x_val.split('/')[-1]].keys()):
                if 'byte_transfers' in csv_files[system.split('/')[-1]][x_val.split('/')[-1]][client.split('/')[-1]].keys():
                    byte_log = csv_files[system.split('/')[-1]][x_val.split('/')[-1]][client.split('/')[-1]]['byte_transfers']
                    timestamps = byte_log['timestamp_ms']
                    lower_bound = timestamps[timestamps < start].max()
                    upper_bound = timestamps[timestamps > end].min()
                    filtered = byte_log[(timestamps > lower_bound) & (timestamps < upper_bound)]
                    total_bytes_sent_per_location = filtered['bytes_sent'].sum() / (no_clients-1)
                    bytes_transfered_matrix[i] = [total_bytes_sent_per_location*dest for dest in bytes_transfered_matrix[i]]
        elif env == 'aws':
            bytes_transfered_matrix = [
                [111,112,113,114,115,116,117,118], # euw1
                [211,212,213,214,215,216,217,218], # euw2
                [311,312,313,314,315,316,317,318], # usw1
                [411,412,413,414,415,416,417,418], # usw2
                [511,512,513,514,515,516,517,518], # use1
                [611,612,613,614,615,616,617,618], # use2
                [711,712,713,714,715,716,717,718], # apne1
                [811,812,813,814,815,816,817,818]  # apne2
            ]
        else:
            bytes_transfered_matrix = [
                [0,0,0,0,0,0,0,0], # euw1
                [0,0,0,0,0,0,0,0], # euw2
                [0,0,0,0,0,0,0,0], # usw1
                [0,0,0,0,0,0,0,0], # usw2
                [0,0,0,0,0,0,0,0], # use1
                [0,0,0,0,0,0,0,0], # use2
                [0,0,0,0,0,0,0,0], # apne1
                [0,0,0,0,0,0,0,0]  # apne2
            ]
        total_bytes_transfered = 0
        total_data_transfer_cost = 0
        for i in range(len(data_transfer_cost_matrix)):
            for j in range(len(data_transfer_cost_matrix[0])):
                total_bytes_transfered += bytes_transfered_matrix[i][j]
                total_data_transfer_cost += data_transfer_cost_matrix[i][j] * bytes_transfered_matrix[i][j]
        total_hourly_cost = vm_cost + total_data_transfer_cost
        byte_transfers[system.split('/')[-1]][x_val.split('/')[-1]] = total_bytes_transfered
        total_costs[system.split('/')[-1]][x_val.split('/')[-1]] = total_hourly_cost

# Write the obtained values to file ('x_var' is the x-axis value for the row). We need to store the following variable (populated above)
# 'x_var_val' (is it does not exist yet), 'throughput', 'latency_percentiles['p50']', 'latency_percentiles['p90']', 'latency_percentiles['p95']', 'latency_percentiles['p99']',
# 'abort_rate', 'bytes_transfered', 'total_hourly_cost'

# For mow we will give 4 latencies (p50, p90, p95, p99) and later pick which one we actually want to plot

colnames = ['x_var']
for system in SYSTEMS_LIST:
    for metric in METRICS_LIST:
        colnames.append(f'{system}_{metric}')
df = pd.DataFrame(data=[], columns=colnames)

for x_val in x_vals:
    x_val = x_val.split('/')[-1]
    new_row = {col: np.nan for col in df.columns}
    if scenario == 'skew':
        new_row['x_var'] = (MAX_YCSBT_HOT_RECORDS - float(x_val)) / MAX_YCSBT_HOT_RECORDS
    else:
        new_row['x_var'] = float(x_val)
    for system in system_dirs:
        sys_name = system.split('/')[-1]
        new_row[f'{sys_name}_throughput'] = throughputs[system.split('/')[-1]][x_val.split('/')[-1]]
        new_row[f'{sys_name}_p50'] = latencies[system.split('/')[-1]][x_val.split('/')[-1]]['p50']
        new_row[f'{sys_name}_p90'] = latencies[system.split('/')[-1]][x_val.split('/')[-1]]['p90']
        new_row[f'{sys_name}_p95'] = latencies[system.split('/')[-1]][x_val.split('/')[-1]]['p95']
        new_row[f'{sys_name}_p99'] = latencies[system.split('/')[-1]][x_val.split('/')[-1]]['p99']
        new_row[f'{sys_name}_aborts'] = abort_rates[system.split('/')[-1]][x_val.split('/')[-1]]
        new_row[f'{sys_name}_bytes'] = byte_transfers[system.split('/')[-1]][x_val.split('/')[-1]]
        new_row[f'{sys_name}_cost'] = total_costs[system.split('/')[-1]][x_val.split('/')[-1]]
    # Append the row
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

# Save the result
df = df.sort_values('x_var')
os.makedirs('/'.join(OUT_CSV_PATH.split('/')[:-1]), exist_ok=True)
df.to_csv(OUT_CSV_PATH, index=False)

# Create new version of plots directly
eval_systems.make_plot(plot=scenario, workload=workload)

print("Done")