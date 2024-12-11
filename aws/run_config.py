import json
import os
import subprocess
from itertools import product
from datetime import datetime
from distutils.dir_util import copy_tree
import signal

from plot_resource_util import plot_monitoring_data

# Function to parse the experiment config and generate a parameter grid
def parse_config(config_file):
    with open(config_file, 'r') as f:
        config = json.load(f)

    base_params = {k: v for k, v in config.items() if not isinstance(v, list)}
    grid_params = {k: v for k, v in config.items() if isinstance(v, list)}

    param_grid = [dict(zip(grid_params.keys(), values)) for values in product(*grid_params.values())]

    return base_params, param_grid

# Function to run a single experiment
def run_experiment(base_params, experiment_params, super_folder):
    # Construct the benchmark parameters
    benchmark = base_params.get("benchmark", "basic")
    image = base_params.get("image", "omraz/seq_eval:latest")
    user = base_params.get("user", "omraz")
    txns = base_params.get("txns", "10")
    clients = base_params.get("clients", "1")
    duration = base_params.get("duration", "10")
    params = ",".join([f"{k}={v}" for k, v in experiment_params.items()])

    # Command to run the benchmark
    cmd = [
        "python3", "tools/admin.py", "benchmark",
        "--image", image,
        "examples/tu_cluster.conf",
        "-u", user,
        "--txns", txns,
        "--clients", clients,
        "--duration", duration,
        "-wl", benchmark,
        "--param", params
    ]

    # Print the command being run
    print(f"Running command: {' '.join(cmd)}")

    # Launch monitor_util.py
    monitor_proc = subprocess.Popen(["python3", "aws/monitor_util.py"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Run the command and capture the output
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    output = result.stdout + result.stderr

    # Terminate the monitoring script
    monitor_proc.send_signal(signal.SIGINT)
    monitor_proc.wait()

    # Extract the timestamp from the output
    extracted_timestamp = None
    for line in output.splitlines():
        if "Tag:" in line:
            extracted_timestamp = line.split()[-1].strip()
            break

    if not extracted_timestamp:
        print(f"Error: Could not extract timestamp for config: {experiment_params}")
        return

    # Create a log file inside the corresponding timestamped folder
    data_dir = f"../data/{extracted_timestamp}"

    # Copy and rename the output folder
    if os.path.exists(data_dir):
        new_folder_name = f"{benchmark}_" + "_".join([f"{k}{v}" for k, v in experiment_params.items()]).replace("=", "")
        new_folder_path = os.path.join(super_folder, new_folder_name)
        try:
            copy_tree(data_dir, new_folder_path)
            print(f"Copied folder to: {new_folder_path}")

            # Save experiment logs to the new folder
            log_file = os.path.join(new_folder_path, "exp.log")
            os.makedirs(new_folder_path, exist_ok=True)
            with open(log_file, "w") as log:
                log.write(output + "\n")

            # Copy utilization.csv to the new folder
            util_csv_path = "utilization.csv"
            if os.path.exists(util_csv_path):
                new_util_csv_path = os.path.join(new_folder_path, "utilization.csv")
                os.rename(util_csv_path, new_util_csv_path)

                # Generate and save the monitoring plot
                plot_path = os.path.join(new_folder_path, "utilization_plot")
                plot_monitoring_data(new_util_csv_path, plot_path)

        except Exception as e:
            print(f"Error: Could not copy folder {data_dir} to {new_folder_path}.\n{e}")
    else:
        print(f"Error: Data folder {data_dir} does not exist")

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run benchmark experiments based on a config file.")
    parser.add_argument("-cfg", "--config", required=True, help="Path to the experiment configuration JSON file.")
    args = parser.parse_args()

    # Load the configuration file
    base_params, param_grid = parse_config(args.config)

    # Create a super folder to hold all experiment results
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    super_folder = f"../data/experiments_{timestamp}"
    os.makedirs(super_folder, exist_ok=True)

    # Run experiments for each configuration
    for experiment_params in param_grid:
        run_experiment(base_params, experiment_params, super_folder)

if __name__ == "__main__":
    main()
