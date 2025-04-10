import os
import subprocess as sp

# --- Config ---
WORKLOAD = 'ycsbt'
DRY_RUN = True # We don't actually run it, just see the commands it will run

venv_activate = "source build_detock/bin/activate"
detock_dir = os.path.expanduser("~/Detock")
image = "omraz/seq_eval:latest"
conf = "examples/tu_cluster.conf"
user = "omraz"
duration = 10
#tag = None #"2025-04-09-14-20-49" # This is extracted from the benchmark command stderr
short_benchmark_log = "benchmark_cmd.log"
log_dir = "data/{}/raw_logs"

single_benchmark_cmd = f"python3 tools/admin.py benchmark --image {image} {conf} -u {user} --txns 2000000 --seed 1 --clients 3000 --duration {duration} -wl basic --param \"mh={1},mp=50\" 2>&1 | tee {short_benchmark_log}"
move_logs_cmd = f"mkdir -p {log_dir} && mv {short_benchmark_log} {log_dir}/"
collect_benchmark_container_cmd = f"docker container logs benchmark &> {log_dir}/benchmark_container.log"
collect_client_cmd = "python3 tools/admin.py collect_client --config {conf} --out-dir data --tag {tag}"

def run_subprocess(cmd, dry_run=False):
    if dry_run:
        return True # TODO: fix properly
    else:
        return sp.run(cmd, shell=True, capture_output=True, text=True)

# For now, we hard code this for the baseline exp (varying MH from 0 to 100) and just for Detock
x_vals = [0, 20, 40, 60, 80, 100]
tags = []
# Run the benchmark for all x_vals and collect all results
for x_val in x_vals:
    cur_benchmark_cmd = single_benchmark_cmd.format(x_val)
    print(f"\n>>> Running: {cur_benchmark_cmd}")
    result = run_subprocess(cur_benchmark_cmd, DRY_RUN) #sp.run(cur_benchmark_cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    print("[stderr]:", result.stderr)
    if result.returncode != 0:
        print(f"Benchmark command failed with exit code {result.returncode}")
        break
    # Get tag from benchmark cmd log
    tag = None
    for line in result.stderr:
        if 'admin INFO: Tag: ' in line:
            tag = line.split('admin INFO: Tag: ')[1]
    if tag is None:
        break
    tags.append(tag)
    log_dir.format(tag)
    # Create directory to store logs and results
    result = run_subprocess(move_logs_cmd, DRY_RUN) #sp.run(move_logs_cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"mkdir and mv commands failed with exit code {result.returncode}")
        break
    # Collect logs from the benchmark container (for throughput)
    result = run_subprocess(collect_benchmark_container_cmd, DRY_RUN) #sp.run(collect_benchmark_container_cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"collect_benchmark_container command failed with exit code {result.returncode}")
        break
    # Collect the metrics from all clients (TODO: add iftop metrics too)
    result = run_subprocess(collect_client_cmd, DRY_RUN) #sp.run(collect_client_cmd.format(conf=conf, tag=tag), shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"collect_client command failed with exit code {result.returncode}")
        break



print("\n All done. You can now copy logs with:")
print(f"scp -r st5:{detock_dir}/data/{tag} ~/Documents/GitHub/Detock/plots/raw_data")