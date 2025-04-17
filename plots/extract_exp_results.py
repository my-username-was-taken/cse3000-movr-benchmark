import os
from os.path import join, isdir
import numpy as np
import csv
import pandas as pd

import eval_systems
'''
Script for extracting the final results out of the logs and CSVs created during the experiment runs.
Intended to be run on own PC, just before the actual plotting of the results.
The script will populate the CSVs in 'plots/data'.
'''

# Define paths
SCENARIOS = ['baseline', "skew", "scalability", "network", "packet_loss", "example"]
scenario_id = 1
exp_raw_data_dir = SCENARIOS[scenario_id] #2025-04-09-14-20-49' #example'
BASE_DIR_PATH = os.path.join("plots/raw_data", exp_raw_data_dir)
#CLIENT_DATA_DIR = os.path.join(BASE_DIR_PATH, "client")
#LOG_DIR = os.path.join(BASE_DIR_PATH, "raw_logs")

out_csv = f'{exp_raw_data_dir}.csv'
OUT_CSV_PATH = os.path.join("plots/data/final", out_csv)
SYSTEMS_LIST = ['Calvin', 'SLOG', 'Detock', 'Caerus', 'Mencius']
METRICS_LIST = ['throughput', 'p50', 'p90', 'p95', 'p99', 'aborts', 'bytes', 'cost']

# Constants for the hourly cost of deploying all the servers on m4.2xlarge VMs (each region has 4 VMs). Price as of 28.3.25
#              euw1  euw2  usw1  usw2  use1  use2  apne1 apne2
vm_cost = 4 * (0.444+0.464+0.468+0.400+0.400+0.400+0.516+0.492)
# The cost of transferring 1GB of data out from the source region (the row). Price as of 28.3.25
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

# Load log files into strings
log_files = {}
tags = {}
throughputs = {}
system_dirs = [join(BASE_DIR_PATH, dir) for dir in os.listdir(BASE_DIR_PATH) if isdir(join(BASE_DIR_PATH, dir))]
for system in system_dirs:
    log_files[system.split('/')[-1]] = {}
    tags[system.split('/')[-1]] = {}
    throughputs[system.split('/')[-1]] = {}
    x_vals = [join(system, dir) for dir in os.listdir(system)]
    for x_val in x_vals:
        log_files[system.split('/')[-1]][x_val.split('/')[-1]] = {}
        with open(join(x_val, 'raw_logs', 'benchmark_cmd.log'), "r", encoding="utf-8") as f:
            log_files[system.split('/')[-1]][x_val.split('/')[-1]]['benchmark_cmd'] = f.read().split('\n')
        with open(join(x_val, 'raw_logs', 'benchmark_container.log'), "r", encoding="utf-8") as f:
            log_files[system.split('/')[-1]][x_val.split('/')[-1]]['benchmark_container'] = f.read().split('\n')
        # Extract tag name from cmd log
        for line in log_files[system.split('/')[-1]][x_val.split('/')[-1]]['benchmark_cmd']:
            if 'admin INFO: Tag: ' in line:
                tag = line.split('admin INFO: Tag: ')[1]
        tags[system.split('/')[-1]][x_val.split('/')[-1]] = tag
        # Extract throughput from container log
        for line in log_files[system.split('/')[-1]][x_val.split('/')[-1]]['benchmark_container']:
            if 'Avg. TPS: ' in line:
                throughput = int(line.split('Avg. TPS: ')[1])
        throughputs[system.split('/')[-1]][x_val.split('/')[-1]] = throughput
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
        # TODO: Actually read real data from a file here
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
    if exp_raw_data_dir == 'skew':
        new_row['x_var'] = (100.0 - float(x_val)) / 100.0
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
df.to_csv(OUT_CSV_PATH, index=False)

# Create new version of plots directly
eval_systems.make_plot(exp_raw_data_dir)

print("Done")