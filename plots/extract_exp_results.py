import os
import numpy as np
import csv
import pandas as pd

'''
Script for extracting the final results out of the logs and CSVs created during the experiment runs.
Intended to be run on own PC, just before the actual plotting of the results.
The script will populate the CSVs in 'plots/data'.
'''

# Define paths
exp_raw_data_dir = 'example' #2025-04-09-14-20-49' #example'
BASE_DIR_PATH = os.path.join("plots/raw_data", exp_raw_data_dir)
CLIENT_DATA_DIR = os.path.join(BASE_DIR_PATH, "client")
LOG_DIR = os.path.join(BASE_DIR_PATH, "raw_logs")

# Give these as arguments. They will determine which cell in the table the generated data points belong to.
scenario_name = 'example'
sys_name = 'Detock'
x_var_val = 10

out_csv = f'{scenario_name}.csv'
OUT_CSV_PATH = os.path.join("plots/data/final", out_csv)
SYSTEMS_LIST = ['Calvin', 'SLOG', 'Detock', 'Caerus', 'Mencius']
METRICS_LIST = ['throughput', 'p50', 'p90', 'p95', 'p99', 'aborts', 'bytes', 'cost']

# Load log files into strings
log_files = {}
for file in os.listdir(LOG_DIR):
    if file.endswith(".log"):
        file_path = os.path.join(LOG_DIR, file)
        with open(file_path, "r", encoding="utf-8") as f:
            file_name = file.split('.')[0]
            log_files[file_name] = f.read().split('\n')
        print(f"Loaded log: {file} (Size: {len(log_files[file_name])} characters)")

# Load CSV files into pandas DataFrames
clients = [obj for obj in os.listdir(CLIENT_DATA_DIR) if os.path.isdir(os.path.join(CLIENT_DATA_DIR, obj))]
csv_files = {}
for client in clients:
    csv_files[client] = {}
    for file in os.listdir(os.path.join(CLIENT_DATA_DIR, client)):
        if file.endswith(".csv"):
            file_path = os.path.join(CLIENT_DATA_DIR, client, file)
            file_name = file.split('.')[0]
            csv_files[client][file_name] = pd.read_csv(file_path)
            print(f"Loaded CSV: {file} (Shape: {csv_files[client][file_name].shape})")

# Get tag from benchmark cmd log
tag = None
for line in log_files['benchmark_cmd']:
    if 'admin INFO: Tag: ' in line:
        tag = line.split('admin INFO: Tag: ')[1]

# Get throughput from benchmark container log
throughput = -1
for line in log_files['benchmark_container']:
    if 'Avg. TPS: ' in line:
        throughput = int(line.split('Avg. TPS: ')[1])

# Get the latency (p50, p90, p95, p99)
all_latencies = []
for client in csv_files.keys():
    csv_files[client]['transactions']["duration"] = csv_files[client]['transactions']["received_at"] - csv_files[client]['transactions']["sent_at"]
    all_latencies.extend(list(csv_files[client]['transactions']["duration"]))

# Compute latency percentiles (and convert to ms)
percentiles = [50, 90, 95, 99]
latency_percentiles = {f"p{p}": np.percentile(np.array(all_latencies) / 1000000, p) for p in percentiles}

# Get the abort rate
abort_rate = -1

total_txns = 0
aborted_txns = 0

for client in csv_files.keys():
    total_txns += csv_files[client]['summary']['single_partition'].iloc[0]
    total_txns += csv_files[client]['summary']['multi_partition'].iloc[0]
    aborted_txns += csv_files[client]['summary']['aborted'].iloc[0]

abort_rate = 100 * aborted_txns / total_txns

# Get the total bytes transfered
# Must collect over all clients
bytes_transfered = 0

# Get the hourly cost of deploying all the servers on m4.2xlarge VMs (each region has 4 VMs). Price as of 28.3.25
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
# Here we will need to consider the duration of the experiemnt
# TODO: Figure out how to make an extrapolation that is an objective estimate (because of start & end anomalies)
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
total_data_transfer_cost = 0
for i in range(len(data_transfer_cost_matrix)):
    for j in range(len(data_transfer_cost_matrix[0])):
        bytes_transfered += bytes_transfered_matrix[i][j]
        total_data_transfer_cost += data_transfer_cost_matrix[i][j] * bytes_transfered_matrix[i][j]

total_hourly_cost = vm_cost + total_data_transfer_cost

# Write the obtained values to file ('x_var' is the x-axis value for the row). We need to store the following variable (populated above)
# 'x_var_val' (is it does not exist yet), 'throughput', 'latency_percentiles['p50']', 'latency_percentiles['p90']', 'latency_percentiles['p95']', 'latency_percentiles['p99']',
# 'abort_rate', 'bytes_transfered', 'total_hourly_cost'

# For mow we will give 4 latencies (p50, p90, p95, p99) and later pick which one we actually want to plot

colnames = ['x_var']
for system in SYSTEMS_LIST:
    for metric in METRICS_LIST:
        colnames.append(f'{system}_{metric}')
if os.path.isfile(OUT_CSV_PATH):
    df = pd.read_csv(OUT_CSV_PATH)
else: # We have to create a new file
    df = pd.DataFrame(data=[], columns=colnames)

# Check if the value already exists in 'x_var'
if (df['x_var'] == x_var_val).any():
    # Update the matching row
    df.loc[df['x_var'] == x_var_val, f'{sys_name}_throughput'] = throughput
    df.loc[df['x_var'] == x_var_val, f'{sys_name}_p50'] = latency_percentiles['p50']
    df.loc[df['x_var'] == x_var_val, f'{sys_name}_p90'] = latency_percentiles['p90']
    df.loc[df['x_var'] == x_var_val, f'{sys_name}_p95'] = latency_percentiles['p95']
    df.loc[df['x_var'] == x_var_val, f'{sys_name}_p99'] = latency_percentiles['p99']
    df.loc[df['x_var'] == x_var_val, f'{sys_name}_aborts'] = abort_rate
    df.loc[df['x_var'] == x_var_val, f'{sys_name}_bytes'] = bytes_transfered
    df.loc[df['x_var'] == x_var_val, f'{sys_name}_cost'] = total_hourly_cost
else:
    # Create a new row with NaNs, except for 'x_var' and the new column
    new_row = {col: np.nan for col in df.columns}
    new_row['x_var'] = x_var_val
    new_row[f'{sys_name}_throughput'] = throughput
    new_row[f'{sys_name}_p50'] = latency_percentiles['p50']
    new_row[f'{sys_name}_p90'] = latency_percentiles['p90']
    new_row[f'{sys_name}_p95'] = latency_percentiles['p95']
    new_row[f'{sys_name}_p99'] = latency_percentiles['p99']
    new_row[f'{sys_name}_aborts'] = abort_rate
    new_row[f'{sys_name}_bytes'] = bytes_transfered
    new_row[f'{sys_name}_cost'] = total_hourly_cost
    # Append the row
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

# Save the result
df.to_csv(OUT_CSV_PATH, index=False)

print("Done")