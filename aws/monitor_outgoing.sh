#!/bin/bash

# Network interface and output CSV file
INTERFACE="enX0"
OUTPUT_CSV="outgoing_traffic_log.csv"
INTERVAL=1

# Function to convert sizes (KB, MB, GB) to Bytes
convert_to_bytes() {
    size=$1
    if [[ $size == *"KB" ]]; then
        echo $(awk "BEGIN {print ${size%KB} * 1024}")
    elif [[ $size == *"MB" ]]; then
        echo $(awk "BEGIN {print ${size%MB} * 1024 * 1024}")
    elif [[ $size == *"GB" ]]; then
        echo $(awk "BEGIN {print ${size%GB} * 1024 * 1024 * 1024}")
    elif [[ $size == *"B" ]]; then
        echo ${size%B}
    else
        echo 0
    fi
}

# Initialize CSV file with headers
echo "Timestamp,Connection,Outgoing_Bytes" > "$OUTPUT_CSV"

echo "Starting outgoing traffic monitoring on interface '$INTERFACE'..."
while true; do
    # Run iftop in batch mode, capture output
    OUTPUT=$(sudo iftop -i "$INTERFACE" -t -s $INTERVAL 2>/dev/null)

    # Parse outgoing cumulative traffic
    echo "$OUTPUT" | awk '/cumulative/ {flag=1; next} /Total/ {flag=0} flag && /=>/ {
        gsub(/[[:space:]]+/, " ");  # Remove excess spaces
        split($0, line, "=>");
        connection=line[1];
        sub(/ .*$/, "", connection);
        traffic=line[2];
        sub(/ .*$/, "", traffic);
        print connection, traffic
    }' | while read -r conn traffic; do
        # Convert traffic to Bytes and append to CSV
        traffic_bytes=$(convert_to_bytes "$traffic")
        timestamp=$(date '+%Y-%m-%d %H:%M:%S')
        echo "$timestamp,$conn,$traffic_bytes" >> "$OUTPUT_CSV"
        echo "$timestamp - $conn: $traffic_bytes Bytes"
    done
done

