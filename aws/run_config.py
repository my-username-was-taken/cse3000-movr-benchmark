import json
import os
import subprocess
from itertools import product
from datetime import datetime
from distutils.dir_util import copy_tree

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

    # Log the command being executed to a file
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_dir = f"../data/{timestamp}"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "exp.log")
    with open(log_file, "w") as log:
        log.write(f"Running command: {' '.join(cmd)}\n")

    # Run the command and capture the output
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    output = result.stdout + result.stderr

    # Log the captured output for debugging
    with open(log_file, "a") as log:
        log.write("Captured output:\n")
        log.write(output + "\n")

    # Extract the timestamp from the output
    extracted_timestamp = None
    for line in output.splitlines():
        if "Tag:" in line:
            extracted_timestamp = line.split()[-1].strip()
            break

    if not extracted_timestamp:
        with open(log_file, "a") as log:
            log.write(f"Error: Could not extract timestamp for config: {experiment_params}\n")
        return

    # Copy and rename the output folder
    data_dir = f"../data/{extracted_timestamp}"
    if os.path.exists(data_dir):
        new_folder_name = f"{benchmark}_" + "_".join([f"{k}{v}" for k, v in experiment_params.items()])
        new_folder_path = os.path.join(super_folder, new_folder_name)
        try:
            copy_tree(data_dir, new_folder_path)
            with open(log_file, "a") as log:
                log.write(f"Copied folder to: {new_folder_path}\n")
        except Exception as e:
            with open(log_file, "a") as log:
                log.write(f"Error: Could not copy folder {data_dir} to {new_folder_path}.\n{e}\n")
    else:
        with open(log_file, "a") as log:
            log.write(f"Error: Data folder {data_dir} does not exist\n")

# Main function
def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run TPC-C benchmark experiments based on a config file.")
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
