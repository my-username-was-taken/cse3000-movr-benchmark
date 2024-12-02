import boto3
import time
import json
import paramiko
import subprocess

# Load configuration
with open("aws/aws.json", "r") as f:
    config = json.load(f)

AWS_USERNAME = config["aws_username"]
REGIONS = config["regions"]
VM_TYPE = config["vm_type"]
AMI_IDS = config["regions"]
KEY_NAME = "my_aws_key"  # Replace with your AWS key pair name

# Initialize AWS clients
ec2_clients = {region: boto3.client("ec2", region_name=region) for region in REGIONS}
instances = []

# Function to launch instances
def launch_instances():
    for region, client in ec2_clients.items():
        print(f"Launching instance in {region}...")
        region_config = config["regions"][region]
        response = client.run_instances(
            ImageId=region_config["ami_id"],
            InstanceType=VM_TYPE,
            KeyName=KEY_NAME,
            MinCount=1,
            MaxCount=1,
            SubnetId=region_config["subnet_id"]
        )
        instance = response["Instances"][0]
        instances.append({"InstanceId": instance["InstanceId"], "Region": region})

# Function to wait until instances are running and fetch their IPs
def wait_for_instances():
    public_ips = []
    for instance in instances:
        region = instance["Region"]
        client = ec2_clients[region]
        instance_id = instance["InstanceId"]

        print(f"Waiting for instance {instance_id} in {region} to be running...")
        waiter = client.get_waiter("instance_running")
        waiter.wait(InstanceIds=[instance_id])

        response = client.describe_instances(InstanceIds=[instance_id])
        instance_info = response["Reservations"][0]["Instances"][0]
        public_ip = instance_info.get("PublicIpAddress")
        print(f"Instance {instance_id} in {region} is running with IP: {public_ip}")
        instance["PublicIp"] = public_ip
        public_ips.append(public_ip)

    return public_ips

# Function to check connectivity between VMs
def test_connectivity(public_ips):
    print("Testing connectivity between VMs...")
    rtt_table = [["Origin", "Destination", "RTT (ms)"]]
    for src_ip in public_ips:
        for dest_ip in public_ips:
            if src_ip != dest_ip:
                rtt = subprocess.run(
                    ["ping", "-c", "1", dest_ip],
                    capture_output=True,
                    text=True,
                )
                rtt_time = "N/A"
                if rtt.returncode == 0:
                    for line in rtt.stdout.splitlines():
                        if "time=" in line:
                            rtt_time = line.split("time=")[1].split(" ")[0]
                rtt_table.append([src_ip, dest_ip, rtt_time])
                print(f"RTT from {src_ip} to {dest_ip}: {rtt_time} ms")

    return rtt_table

# Function to deploy monitoring script on VMs
def deploy_monitoring_script(public_ips):
    print("Deploying monitoring script to VMs...")
    monitoring_script = """
#!/bin/bash
while true; do
    echo "$(date) | CPU: $(top -bn1 | grep 'Cpu(s)' | awk '{print $2+$4}')% | Mem: $(free -m | awk 'NR==2{printf \"%s/%s MB\", $3,$2 }') | Disk: $(df -h / | awk 'NR==2{print $3\"/\"$2}') | Network: $(ifconfig eth0 | grep 'RX bytes' | awk '{print $2 $6}')"
    sleep 1
done > /var/log/resource_monitor.log &
"""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    for ip in public_ips:
        try:
            print(f"Connecting to {ip}...")
            ssh.connect(hostname=ip, username="ubuntu", key_filename="~/.ssh/my_aws_key.pem")
            stdin, stdout, stderr = ssh.exec_command(f"echo '{monitoring_script}' > /tmp/monitor.sh && chmod +x /tmp/monitor.sh && /tmp/monitor.sh")
            print(stdout.read().decode(), stderr.read().decode())
        except Exception as e:
            print(f"Failed to connect to {ip}: {e}")

    ssh.close()

# Main function
if __name__ == "__main__":
    # Step 1: Launch instances
    launch_instances()

    # Step 2: Wait for instances and get public IPs
    public_ips = wait_for_instances()

    # Step 3: Test connectivity
    rtt_table = test_connectivity(public_ips)

    # Step 4: Deploy monitoring script
    deploy_monitoring_script(public_ips)

    # Step 5: Print results
    print("\nInstance Information:")
    for instance in instances:
        print(f"Instance {instance['InstanceId']} in {instance['Region']} with IP {instance['PublicIp']}")

    print("\nRTT Table:")
    for row in rtt_table:
        print("\t".join(row))
