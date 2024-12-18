import subprocess
import re
import csv
import time
from datetime import datetime

# Helper function to convert cumulative sizes to bytes
def convert_to_bytes(size_str):
    size_str = size_str.strip().lower()
    if size_str.endswith("kb"):
        return float(size_str[:-2]) * 1024
    elif size_str.endswith("mb"):
        return float(size_str[:-2]) * 1024 * 1024
    elif size_str.endswith("gb"):
        return float(size_str[:-2]) * 1024 * 1024 * 1024
    elif size_str.endswith("b"):
        return float(size_str[:-1])
    return 0  # Return 0 if no recognizable size format

# Function to monitor and parse iftop output for outgoing traffic
def monitor_iftop_outgoing(interface="enX0", output_csv="network_traffic_log.csv", interval=1):
    # Initialize an empty set to store all unique connections
    connections = set()

    # Initialize CSV file with headers
    with open(output_csv, "w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["Timestamp"])  # Initialize with "Timestamp" column

    # Start monitoring
    print(f"Starting outgoing traffic monitoring on interface '{interface}'...")

    try:
        while True:
            # Run the iftop command and capture output
            result = subprocess.run(
                ["sudo", "iftop", "-i", interface, "-t"],
                capture_output=True,
                text=True,
                timeout=5
            )
            output = result.stdout
            print(output)

            # Parse connections and cumulative traffic
            current_data = {}
            lines = output.splitlines()
            cumulative_section = False

            for line in lines:
                # Identify the cumulative section
                if "cumulative" in line.lower():
                    cumulative_section = True
                    continue

                # Parse outgoing traffic lines
                if cumulative_section and line.strip():
                    match = re.match(r"^\s*\d+\s+([\w\.\-\:]+).*?=>\s+([\d\.]+\w+)", line)
                    if match:
                        connection = match[1]
                        traffic = match[2]
                        current_data[connection] = convert_to_bytes(traffic)

            # Update the set of all connections
            connections.update(current_data.keys())

            # Write data to CSV file
            with open(output_csv, "r+", newline="") as csv_file:
                reader = csv.reader(csv_file)
                writer = csv.writer(csv_file)
                headers = next(reader, ["Timestamp"])  # Read existing headers

                # Update headers if new connections are found
                if set(headers) != set(["Timestamp"] + list(connections)):
                    headers = ["Timestamp"] + list(connections)
                    csv_file.seek(0)  # Go to the beginning
                    all_rows = [headers] + list(reader)
                    csv_file.truncate(0)  # Clear file
                    writer.writerows(all_rows)
                else:
                    headers = headers

                # Write a new row with current traffic data
                row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
                for conn in headers[1:]:
                    row.append(current_data.get(conn, 0))  # Default to 0 if no data
                writer.writerow(row)

            print(f"Logged outgoing traffic at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            time.sleep(interval)

    except KeyboardInterrupt:
        print("Monitoring stopped by user.")
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    # You can customize the interface name and CSV output path
    monitor_iftop_outgoing(interface="enX0", output_csv="outgoing_traffic_log.csv", interval=1)
