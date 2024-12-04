import psutil
import time
import csv
from datetime import datetime

start_time = time.time()
start_timestamp = str(datetime.utcfromtimestamp(start_time)).replace(' ', '_').replace(':','_')[:19]
output_file = f"utilization_{start_timestamp}.csv"

# Create the CSV file with the header
with open(output_file, mode="w", newline="") as file:
    writer = csv.writer(file)
    writer.writerow(["Time", "CPU_util", "Mem_util", "Net_util", "Disk_util"])

# Monitoring function
def monitor():
    net_prev = psutil.net_io_counters()
    disk_prev = psutil.disk_io_counters()

    while True:
        elapsed_time = int(time.time() - start_time)

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
            writer.writerow([elapsed_time, round(cpu_util, 2), round(mem_util, 2), round(net_util, 2), round(disk_util, 2)])

# Run the monitoring function in the background
if __name__ == "__main__":
    import threading
    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()

    print(f"Monitoring started. Output will be saved to '{output_file}'. Press Ctrl+C to stop.")
    while True:
        time.sleep(1)
