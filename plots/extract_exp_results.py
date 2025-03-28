import os
import numpy
import csv
import pandas as pd

'''
Script for extracting the final results out of the logs and CSVs created during the experiment runs.
Intended to be run on own PC, just before the actual plotting of the results.
The script will populate the CSVs in 'plots/data'.
'''

# Define paths
exp_raw_data_dir = 'example'
BASE_DIR_PATH = os.path.join("plots/raw_data", exp_raw_data_dir)
CSV_DIR = os.path.join(BASE_DIR_PATH, "raw_csvs")
LOG_DIR = os.path.join(BASE_DIR_PATH, "raw_logs")

out_csv = 'baseline.csv'
OUT_CSV_PATH = os.path.join("plots/data", out_csv)

# Load log files into strings
log_files = {}
for file in os.listdir(LOG_DIR):
    if file.endswith(".txt"):
        file_path = os.path.join(LOG_DIR, file)
        with open(file_path, "r", encoding="utf-8") as f:
            file_name = file.split('.')[0]
            log_files[file_name] = f.read().split('\n')
        print(f"Loaded log: {file} (Size: {len(log_files[file_name])} characters)")

# Load CSV files into pandas DataFrames
csv_files = {}
for file in os.listdir(CSV_DIR):
    if file.endswith(".csv"):
        file_path = os.path.join(CSV_DIR, file)
        file_name = file.split('.')[0]
        csv_files[file_name] = pd.read_csv(file_path)
        print(f"Loaded CSV: {file} (Shape: {csv_files[file_name].shape})")

# Get tag from benchmark cmd log
tag = None
for line in log_files['benchmark_cmd_log']:
    if 'admin INFO: Tag: ' in line:
        tag = line.split('admin INFO: Tag: ')[1]

# Get throughput from benchmark container log
throughput = -1
for line in log_files['benchmark_container_log']:
    if 'Avg. TPS: ' in line:
        throughput = int(line.split('Avg. TPS: ')[1])

# Get the latency (p50, p90, p95, p99)
# Must collect over all clients
latencies = []

# Get the aborts
# Must collect over all clients
aborts = -1

# Get the total bytes transfered
# Must collect over all clients
bytes_transfered = -1

# Get the hourly cost of deployment
# Must collect over all clients
cost = -1

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
# TODO: FIgure out how to make an extrapolation that is an objective estimate (because of start & end anomalies)
bytes_transfered_matrix = [
    [],
    [],
    [],
    [],
    [],
    [],
    [],
    []
]
total_data_transfer_cost = 0
for i in range(len(data_transfer_cost_matrix)):
    for j in range(len(data_transfer_cost_matrix[0])):
        total_data_transfer_cost += data_transfer_cost_matrix[i][j] * bytes_transfered_matrix[i][j]

total_hourly

# Write the obtained values to file





print("Done")