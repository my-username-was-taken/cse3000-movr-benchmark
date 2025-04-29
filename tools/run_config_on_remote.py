import os
import sys
import subprocess as sp
import shutil

import simulate_network

# --- Config ---
MACHINE = 'st5'
WORKLOAD = 'ycsbt'
DRY_RUN = False # We don't actually run it, just see the commands it will run
FINAL_FOLDER = 'network'
BASIC_IFTOP_CMD = 'iftop 2>&1'

#INTERFACE = 'eno33np0' # TODO: Check!!! May differ for AWS
interfaces = {}

#venv_activate = "source build_detock/bin/activate" # If running this script on the target machine, we will anyway have this env activated
detock_dir = os.path.expanduser("~/Detock")
systems_to_test = ['Detock']
image = "omraz/seq_eval:latest"
conf = "examples/tu_cluster.conf"
user = "omraz"
duration = 60
#tag = None #"2025-04-09-14-20-49" # This is extracted from the benchmark command stderr
short_benchmark_log = "benchmark_cmd.log"
log_dir = "data/{}/raw_logs"
cur_log_dir = None

if FINAL_FOLDER == 'baseline':
    benchmark_params = "\"mh={},mp=50\"" # For the baseline scenario
    clients = 3000
    x_vals = [0, 20, 40, 60, 80, 100]
elif FINAL_FOLDER == 'skew':
    benchmark_params = "\"mh=50,mp=50,hot={}\""
    clients = 3000
    x_vals = [1, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 210, 220, 230, 240, 250]
elif FINAL_FOLDER == 'scalability':
    benchmark_params = "\"mh=50,mp=50\""
    clients = None
    x_vals = [1, 10, 100, 1000, 10000, 1000000]
elif FINAL_FOLDER == 'network':
    benchmark_params = "\"mh=50,mp=50\""
    clients = 3000
    x_vals = [0, 10, 50, 100, 250, 500, 1000]
elif FINAL_FOLDER == 'packet_loss':
    benchmark_params = "\"mh=50,mp=50\""
    clients = 3000
    x_vals = [0, 0.1, 0.2, 0.5, 1, 2, 5, 10]

single_ycsbt_benchmark_cmd = "python3 tools/admin.py benchmark --image {image} {conf} -u {user} --txns 2000000 --seed 1 --clients {clients} --duration {duration} -wl basic --param {benchmark_params} 2>&1 | tee {short_benchmark_log}"
single_tpcc_benchmark_cmd = f""
if WORKLOAD == 'ycsbt':
    single_benchmark_cmd = single_ycsbt_benchmark_cmd
elif WORKLOAD == 'tpcc':
    single_benchmark_cmd = single_tpcc_benchmark_cmd
collect_client_cmd = "python3 tools/admin.py collect_client --config {conf} --out-dir data --tag {tag}"

def run_subprocess(cmd, dry_run=False):
    if dry_run:
        print(f"Would have run command: {cmd}")
        return True # TODO: fix properly
    else:
        return sp.run(cmd, shell=True, capture_output=True, text=True)

def get_ips_from_conf(conf_path):
    with open(conf_path, "r") as f:
        conf_data = f.readlines()
    ips_used = set()
    for line in conf_data:
        if '    addresses: ' in line:
            ips_used.add(line.split('    addresses: "')[1].split('"')[0])
    ips_used = list(ips_used)
    return ips_used

def get_network_interfaces(ips_used):
    interface = run_subprocess(BASIC_IFTOP_CMD).stdout.split('\n')[0].split('interface: ')[1]
    print(f"This machine uses the network interface: {interface}")
    for ip in ips_used:
        try:
            ssh_target = f"{user}@{ip}" if user else ip
            ssh_cmd = f"ssh {ssh_target} '{BASIC_IFTOP_CMD}'"
            result = run_subprocess(ssh_cmd, DRY_RUN)
            print(f"Result is: {result}")
            interfaces[ip] = result.stdout.split('\n')[0].split('interface: ')[1]
        except:
            print(f"Unable to find interface for IP: {ip}")

ips_used = get_ips_from_conf(conf_path=conf)
print(f"The IPs used in this experiment are: {ips_used}")
get_network_interfaces(ips_used=ips_used)

os.makedirs(f'data/{FINAL_FOLDER}', exist_ok=True)
# For now, we hard code this for the baseline exp (varying MH from 0 to 100) and just for Detock
tags = []
for system in systems_to_test:
    print("#####################")
    print(f"Testing system: {system}")
    os.makedirs(f'data/{FINAL_FOLDER}/{system}', exist_ok=True)
    # Run the benchmark for all x_vals and collect all results
    for x_val in x_vals:
        print("---------------------")
        print(f"Running experiment with x_val: {x_val}")
        tag = None
        cur_benchmark_params = benchmark_params.format(x_val) # Works for both baseline AND skew
        cur_clients = clients if clients is not None else x_val
        cur_benchmark_cmd = single_benchmark_cmd.format(image=image, conf=conf, user=user, clients=cur_clients, duration=duration, benchmark_params=cur_benchmark_params, short_benchmark_log=short_benchmark_log)
        print(f"\n>>> Running: {cur_benchmark_cmd}")
        if FINAL_FOLDER == 'network':
            # Emulate the network conditions first
            delay = f"{x_val}ms"
            jitter = f"{int(x_val / 10)}ms"
            loss = "0%"
        elif FINAL_FOLDER == 'packet_loss':
            delay = "0ms"
            jitter = "0ms"
            loss = f"{x_val}%"
        # Note: the netem command may require allowing passwordless sudo for tc commands
        # I.e., add something like 'omraz ALL=(ALL) NOPASSWD: /usr/sbin/tc' to 'sudo visudo'
        if FINAL_FOLDER == 'network' or FINAL_FOLDER == 'packet_loss':
            simulate_network.apply_netem(delay=delay, jitter=jitter, loss=loss, ips=interfaces, user=user)
        result = run_subprocess(cur_benchmark_cmd, DRY_RUN) #sp.run(cur_benchmark_cmd, shell=True, capture_output=True, text=True)
        if FINAL_FOLDER == 'network' or FINAL_FOLDER == 'packet_loss':
            # Remove emulated network conditions first
            simulate_network.remove_netem(ips=interfaces, user=user)
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
print("============================================")