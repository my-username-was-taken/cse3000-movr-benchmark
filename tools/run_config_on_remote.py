import os
import subprocess as sp
import time
import shutil

# --- Config ---
MACHINE = 'st5'
WORKLOAD = 'ycsbt'
DRY_RUN = False # We don't actually run it, just see the commands it will run
FINAL_FOLDER = 'baseline'

#venv_activate = "source build_detock/bin/activate" # If running this script on the target machine, we will anyway have this env activated
detock_dir = os.path.expanduser("~/Detock")
systems_to_test = ['Detock']
image = "omraz/seq_eval:latest"
conf = "examples/tu_cluster.conf"
user = "omraz"
duration = 10
#tag = None #"2025-04-09-14-20-49" # This is extracted from the benchmark command stderr
short_benchmark_log = "benchmark_cmd.log"
log_dir = "data/{}/raw_logs"
cur_log_dir = None

benchmark_params = "\"mh={},mp=50\"" # For the baseline scenario
single_benchmark_cmd = f"python3 tools/admin.py benchmark --image {image} {conf} -u {user} --txns 2000000 --seed 1 --clients 3000 --duration {duration} -wl basic --param {benchmark_params} 2>&1 | tee {short_benchmark_log}"
collect_client_cmd = "python3 tools/admin.py collect_client --config {conf} --out-dir data --tag {tag}"

def run_subprocess(cmd, dry_run=False):
    if dry_run:
        print(f"Would have run command: {cmd}")
        return True # TODO: fix properly
    else:
        return sp.run(cmd, shell=True, capture_output=True, text=True)

os.makedirs(f'data/{FINAL_FOLDER}', exist_ok=True)

# For now, we hard code this for the baseline exp (varying MH from 0 to 100) and just for Detock
x_vals = [0, 20, 40, 60, 80, 100]
tags = []
for system in systems_to_test:
    print("#####################")
    print(f"Testing system: {system}")
    os.mkdir(f'data/{FINAL_FOLDER}/{system}')
    # Run the benchmark for all x_vals and collect all results
    for x_val in x_vals:
        print("---------------------")
        print(f"Running experiment with x_val: {x_val}")
        tag = None
        cur_benchmark_cmd = single_benchmark_cmd.format(x_val)
        print(f"\n>>> Running: {cur_benchmark_cmd}")
        result = run_subprocess(cur_benchmark_cmd, DRY_RUN) #sp.run(cur_benchmark_cmd, shell=True, capture_output=True, text=True)
        benchmark_cmd_log = ['']
        if not DRY_RUN:
            print(result.stdout)
            print("[stderr]:", result.stderr)
            if result.returncode != 0:
                print(f"Benchmark command failed with exit code {result.returncode}")
                #break
            # Get tag from benchmark cmd log
            benchmark_cmd_log = result.stdout.split('\n')
            for line in benchmark_cmd_log:
                if 'admin INFO: Tag: ' in line:
                    tag = line.split('admin INFO: Tag: ')[1]
        else:
            tag = 'dry_run'
        if tag is None:
            break
        tags.append(tag)
        cur_log_dir = log_dir.format(tag)
        # Make new (local) dir for storing result
        os.makedirs(cur_log_dir, exist_ok=True)
        # Store captured logs into file
        with open(f"{cur_log_dir}/{short_benchmark_log}", 'w') as f:
            for line in benchmark_cmd_log:
                f.write(f"{line}\n")
        #move_logs_cmd = f"mkdir -p {cur_log_dir} && mv {short_benchmark_log} {cur_log_dir}/"
        collect_benchmark_container_cmd = f"docker container logs benchmark 2>&1"
        # Create directory to store logs and results
        #result = run_subprocess(move_logs_cmd, DRY_RUN) #sp.run(move_logs_cmd, shell=True, capture_output=True, text=True)
        #if hasattr(result, "returncode") and result.returncode != 0:
        #    print(f"mkdir and mv commands failed with exit code {result.returncode}")
        #    break
        # Collect logs from the benchmark container (for throughput)
        result = run_subprocess(collect_benchmark_container_cmd, DRY_RUN) #sp.run(collect_benchmark_container_cmd, shell=True, capture_output=True, text=True)
        with open(f"{cur_log_dir}/benchmark_container.log", 'w') as f:
            for line in result.stdout.split('\n'):
                f.write(f"{line}\n")
        if hasattr(result, "returncode") and result.returncode != 0:
            print(f"collect_benchmark_container command failed with exit code {result.returncode}")
            break
        # Collect the metrics from all clients (TODO: add iftop metrics too)
        result = run_subprocess(collect_client_cmd.format(conf=conf, tag=tag), DRY_RUN) #sp.run(collect_client_cmd.format(conf=conf, tag=tag), shell=True, capture_output=True, text=True)
        if hasattr(result, "returncode") and result.returncode != 0:
            print(f"collect_client command failed with exit code {result.returncode}")
            break
        # Rename folder accordingly
        shutil.move(f'data/{tag}', f'data/{FINAL_FOLDER}/{system}/{x_val}')
        #os.rename(f'data/{FINAL_FOLDER}/{system}/{tag}', f'data/{FINAL_FOLDER}/{system}/{x_val}')

print("#####################")
print(f"\n All {FINAL_FOLDER} experiments done. You can now copy logs with:")
print(f"scp -r {MACHINE}:{detock_dir}/data/{FINAL_FOLDER}/* ~/Documents/GitHub/Detock/plots/raw_data/{FINAL_FOLDER}")
