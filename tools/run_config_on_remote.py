import sys
sys.path.append('../')

import os
import subprocess as sp
import shutil
import argparse

from .aws import monitor_util
import simulate_network

VALID_SCENARIOS = ['baseline', 'skew', 'scalability', 'network', 'packet_loss', 'sunflower']
VALID_WORKLOADS = ['ycsbt', 'tpcc'] # TODO: Add your own benchmark to this list

# Argument parser
parser = argparse.ArgumentParser(description="Run Detock experiment with a given scenario.")
parser.add_argument('-s',  '--scenario', default='network', choices=VALID_SCENARIOS, help='Type of experiment scenario to run (default: baseline)')
parser.add_argument('-w',  '--workload', default='ycsbt', choices=VALID_WORKLOADS, help='Workload to run (default: ycsbt)')
parser.add_argument('-c',  '--conf', default='examples/tu_cluster.conf', help='.conf file used for experiment')
parser.add_argument('-d',  '--duration', default=10, help='Duration (in seconds) of a single experiment')
parser.add_argument('-dr', '--dry_run', default=False, help='Whether to run this as a dry run')
parser.add_argument('-u',  '--user', default="omraz", help='Username when logging into a remote machine')
parser.add_argument('-m',  '--machine', default="st5", help='The machine from which this script is (used to write out the scp command for collecting the results.)')

args = parser.parse_args()
scenario = args.scenario
workload = args.workload
conf = args.conf
duration = args.duration
dry_run = args.dry_run
user = args.user
machine = args.machine

print(f"Running scenario: '{scenario}' and workload: '{workload}'")

BASIC_IFTOP_CMD = 'iftop 2>&1'

interfaces = {}

#venv_activate = "source build_detock/bin/activate" # If running this script on the target machine, we will anyway have this env activated
detock_dir = os.path.expanduser("~/Detock")
systems_to_test = ['Detock']
image = "omraz/seq_eval:latest"
#tag = None #"2025-04-09-14-20-49" # This is extracted from the benchmark command stderr
short_benchmark_log = "benchmark_cmd.log"
log_dir = "data/{}/raw_logs"
cur_log_dir = None

if scenario == 'baseline':
    benchmark_params = "\"mh={},mp=50\"" # For the baseline scenario
    clients = 3000
    x_vals = [0, 20, 40, 60, 80, 100]
elif scenario == 'skew':
    benchmark_params = "\"mh=50,mp=50,hot={}\""
    clients = 3000
    x_vals = [1, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 200, 210, 220, 230, 240, 250]
elif scenario == 'scalability':
    benchmark_params = "\"mh=50,mp=50\""
    clients = None
    x_vals = [1, 10, 100, 1000, 10000, 1000000]
elif scenario == 'network':
    benchmark_params = "\"mh=50,mp=50\""
    clients = 3000
    x_vals = [0, 10, 50, 100, 250, 500, 1000]
elif scenario == 'packet_loss':
    benchmark_params = "\"mh=50,mp=50\""
    clients = 3000
    x_vals = [0, 0.1, 0.2, 0.5, 1, 2, 5, 10]
elif scenario == 'sunflower':
    raise Exception("The sunflower scenario is not yet implemented")

single_ycsbt_benchmark_cmd = "python3 tools/admin.py benchmark --image {image} {conf} -u {user} --txns 2000000 --seed 1 --clients {clients} --duration {duration} -wl basic --param {benchmark_params} 2>&1 | tee {short_benchmark_log}"
single_tpcc_benchmark_cmd = f""
if workload == 'ycsbt':
    single_benchmark_cmd = single_ycsbt_benchmark_cmd
elif workload == 'tpcc':
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
            result = run_subprocess(ssh_cmd, dry_run)
            print(f"Result is: {result}")
            interfaces[ip] = result.stdout.split('\n')[0].split('interface: ')[1]
        except:
            print(f"Unable to find interface for IP: {ip}")

def start_net_monitor(user, interfaces):
    for ip, iface in interfaces.items():  # assuming interfaces is a dict {ip: iface}
        cmd = (
            f"ssh {user}@{ip} '"
            f"echo \"timestamp_ms,bytes_sent\" > net_traffic.csv; "
            f"prev=$(awk '\\''$1 ~ \"{iface}:\" {{print $10}}'\\'' /proc/net/dev); "
            f"while true; do "
            f"sleep 1; "
            f"now=$(date +%s%3N); "
            f"curr=$(awk '\\''$1 ~ \"{iface}:\" {{print $10}}'\\'' /proc/net/dev); "
            f"delta=$((curr - prev)); "
            f"echo \"$now,$delta\" >> net_traffic.csv; "
            f"prev=$curr; "
            f"done' > /dev/null 2>&1 &"
        )
        result = sp.run(cmd, shell=True)
        if hasattr(result, "returncode") and result.returncode != 0:
            print(f"Launch network monitoring command in ip '{ip}' failed with exit code {result.returncode}!")

def stop_and_collect_monitor(user, interfaces):
    for ip in interfaces.keys():
        sp.run(f"ssh {user}@{ip} pkill -f net_traffic.csv", shell=True)
        result = sp.run(f"scp {user}@{ip}:net_traffic.csv data/{tag}/net_traffic_{ip.replace('.', '_')}.csv", shell=True)
        if hasattr(result, "returncode") and result.returncode != 0:
            print(f"Collecting network monitoring command failed with exit code {result.returncode}!")
            break

ips_used = get_ips_from_conf(conf_path=conf)
print(f"The IPs used in this experiment are: {ips_used}")
get_network_interfaces(ips_used=ips_used)

os.makedirs(f'data/{scenario}', exist_ok=True)
# For now, we hard code this for the baseline exp (varying MH from 0 to 100) and just for Detock
tags = []
for system in systems_to_test:
    print("#####################")
    print(f"Testing system: {system}")
    os.makedirs(f'data/{scenario}/{system}', exist_ok=True)
    # Run the benchmark for all x_vals and collect all results
    for x_val in x_vals:
        print("---------------------")
        print(f"Running experiment with x_val: {x_val}")
        tag = None
        cur_benchmark_params = benchmark_params.format(x_val) # Works for: baseline, skew, scalability, network, packet_loss
        cur_clients = clients if clients is not None else x_val
        cur_benchmark_cmd = single_benchmark_cmd.format(image=image, conf=conf, user=user, clients=cur_clients, duration=duration, benchmark_params=cur_benchmark_params, short_benchmark_log=short_benchmark_log)
        print(f"\n>>> Running: {cur_benchmark_cmd}")
        if scenario == 'network':
            # Emulate the network conditions first
            delay = f"{x_val}ms"
            jitter = f"{int(x_val / 10)}ms"
            loss = "0%"
        elif scenario == 'packet_loss':
            delay = "0ms"
            jitter = "0ms"
            loss = f"{x_val}%"
        # Note: the netem command may require allowing passwordless sudo for tc commands
        # I.e., add something like 'omraz ALL=(ALL) NOPASSWD: /usr/sbin/tc' to 'sudo visudo'
        if scenario == 'network' or scenario == 'packet_loss':
            simulate_network.apply_netem(delay=delay, jitter=jitter, loss=loss, ips=interfaces, user=user)
            print(f"All servers simulating an additional delay of {delay}, jitter of {jitter}, and packet loss of {loss}")
        # Start monitoring the outbound traffic on remote machines
        start_net_monitor(user=user, interfaces=interfaces)
        # THE ACTUAL EXPERIMENT RUN
        result = run_subprocess(cur_benchmark_cmd, dry_run) #sp.run(cur_benchmark_cmd, shell=True, capture_output=True, text=True)
        # Print and collect output
        benchmark_cmd_log = ['']
        if not dry_run:
            print(result.stdout)
            print("[stderr]:", result.stderr)
            if result.returncode != 0:
                print(f"Benchmark command failed with exit code {result.returncode}!")
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
        # Remove any network restrictions
        if scenario == 'network' or scenario == 'packet_loss':
            # Remove emulated network conditions first
            simulate_network.remove_netem(ips=interfaces, user=user)
            print(f"Network settings on all servers back to normal!")
        collect_benchmark_container_cmd = f"docker container logs benchmark 2>&1"
        # Collect logs from the benchmark container (for throughput)
        result = run_subprocess(collect_benchmark_container_cmd, dry_run) #sp.run(collect_benchmark_container_cmd, shell=True, capture_output=True, text=True)
        with open(f"{cur_log_dir}/benchmark_container.log", 'w') as f:
            for line in result.stdout.split('\n'):
                f.write(f"{line}\n")
        if hasattr(result, "returncode") and result.returncode != 0:
            print(f"collect_benchmark_container command failed with exit code {result.returncode}!")
            break
        # Collect the metrics from all clients (TODO: add iftop metrics too)
        result = run_subprocess(collect_client_cmd.format(conf=conf, tag=tag), dry_run) #sp.run(collect_client_cmd.format(conf=conf, tag=tag), shell=True, capture_output=True, text=True)
        if hasattr(result, "returncode") and result.returncode != 0:
            print(f"collect_client command failed with exit code {result.returncode}!")
            break
        # Stop and collect network monitoring script
        stop_and_collect_monitor(user, interfaces)
        # Rename folder accordingly
        shutil.move(f'data/{tag}', f'data/{scenario}/{system}/{x_val}')

print("#####################")
print(f"\n All {scenario} experiments done. You can now copy logs with:")
print(f"scp -r {machine}:{detock_dir}/data/{scenario} ~/Documents/GitHub/Detock/plots/raw_data/{workload}/{scenario}")
print("============================================")