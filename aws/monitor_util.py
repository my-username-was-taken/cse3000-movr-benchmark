import os
import subprocess as sp
from subprocess import Popen, PIPE
import shlex
import psutil
import time
import csv
from datetime import datetime
import threading

start_time = time.time()
start_timestamp = str(datetime.utcfromtimestamp(start_time)).replace(' ', '_').replace(':','_')[:19]
output_file = f"utilization.csv"
#output_file = f"utilization_{start_timestamp}.csv"

network_output_file = f'network_traffic.csv'

# Create the CSV file with the header
with open(output_file, mode="w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["Timestamp", "Elapsed_time", "CPU_util", "Mem_util", "Net_util", "Disk_util"])

# Monitoring function
def monitor_perc_util():
    net_prev = psutil.net_io_counters()
    disk_prev = psutil.disk_io_counters()

    while True:
        cur_time = time.time()
        elapsed_time = int(cur_time - start_time)

        # Collect utilization data
        cpu_util = psutil.cpu_percent(interval=1)
        mem_util = psutil.virtual_memory().percent
        net_curr = psutil.net_io_counters()
        net_util = (net_curr.bytes_sent + net_curr.bytes_recv - net_prev.bytes_sent - net_prev.bytes_recv) / 1_000_000  # In MB/s
        disk_curr = psutil.disk_io_counters()
        disk_util = (disk_curr.read_bytes + disk_curr.write_bytes - disk_prev.read_bytes - disk_prev.write_bytes) / 1_000_000  # In MB/s

        net_prev = net_curr
        disk_prev = disk_curr

        # Write data to CSV
        with open(output_file, mode="a", newline="") as file:
            writer = csv.writer(file)
            writer.writerow([cur_time, elapsed_time, round(cpu_util, 2), round(mem_util, 2), round(net_util, 2), round(disk_util, 2)])

def monitor_net():
    #proc = Popen('python3 monitor_network.py >> net_raw_output.log', stdout=PIPE, stderr=PIPE)
    #proc = Popen('python3 monitor_network.py', stdout=PIPE, stderr=PIPE)
    sp.run('python3 monitor_network.py', shell=True)

def log_iftop_output():
    cmd = ["sudo", "iftop", "-i", "enX0", "-t", "-B"]
    log_file = "iftop_raw_output.log"

    with sp.Popen(cmd, stdout=sp.PIPE, stderr=sp.STDOUT, bufsize=1, text=True) as proc, open(log_file, "a") as log:
        block = []
        for line in proc.stdout:
            if line.strip() == "":  # Empty line indicates end of a block
                if block:
                    # Add a timestamp to the entire block
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    log.write(f"{timestamp}\n")
                    log.writelines(block)
                    log.write("\n")  # Separate blocks with an empty line
                    log.flush()
                    block = []
            else:
                block.append(line)

        # Handle any remaining output
        if block:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log.write(f"{timestamp}\n")
            log.writelines(block)
            log.write("\n")

# Run the monitoring function in the background
if __name__ == "__main__":
    print(f"Monitoring started. Output will be saved to '{output_file}'. Press Ctrl+C to stop.")
    prec_util_thread = threading.Thread(target=monitor_perc_util, daemon=True)
    #prec_util_thread.start()

    monitor_net_thread = threading.Thread(target=monitor_net, daemon=True)
    monitor_net_thread.start()

    # Not running the send function as a thread, otherwise it hangs
    log_iftop_output()
    #net_traffic_thread = threading.Thread(target=log_iftop_output, daemon=True)
    #net_traffic_thread.start()

    while True:
        time.sleep(1)
