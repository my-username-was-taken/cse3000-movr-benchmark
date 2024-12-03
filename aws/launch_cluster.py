import boto3
import os
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
AMI_IDS = config["regions"]  # Contains AMI and Subnet for each region
instances = []

# Initialize AWS clients for each region
ec2_clients = {region: boto3.client("ec2", region_name=region) for region in REGIONS.keys()}


def ensure_key_pair(region):
    """
    Ensures a key pair named 'my_aws_key_<region>' exists in the specified region.
    If it doesn't exist, creates it and saves the private key locally.
    """
    key_name = f"my_aws_key_{region}"
    client = ec2_clients[region]
    try:
        # Check if the key pair already exists
        client.describe_key_pairs(KeyNames=[key_name])
        print(f"Key pair '{key_name}' already exists in {region}.")
    except client.exceptions.ClientError as e:
        if "InvalidKeyPair.NotFound" in str(e):
            # Create the key pair
            print(f"Key pair '{key_name}' not found in {region}. Creating...")
            response = client.create_key_pair(KeyName=key_name)
            key_material = response["KeyMaterial"]

            # Save the private key to a local file
            private_key_file = f"keys/{key_name}.pem"
            with open(private_key_file, "w") as f:
                f.write(key_material)
            os.chmod(private_key_file, 0o400)
            print(f"Key pair '{key_name}' created. Private key saved to '{private_key_file}'.")
        else:
            raise


def launch_instances():
    """
    Launches one EC2 instance in each region specified in the configuration.
    """
    for region, client in ec2_clients.items():
        region_config = REGIONS[region]
        ensure_key_pair(region)  # Ensure the key pair exists
        key_name = f"my_aws_key_{region}"

        print(f"Launching instance in {region}...")
        ec2_client = ec2_clients[region]
        response = ec2_client.run_instances(
            ImageId=region_config["ami_id"],
            InstanceType=config["vm_type"],
            KeyName=key_name,
            MinCount=1,
            MaxCount=1,
            NetworkInterfaces=[
                {
                    "SubnetId": region_config["subnet_id"],
                    "DeviceIndex": 0,
                    "AssociatePublicIpAddress": True,  # This ensures a public IP is assigned
                }
            ],
            TagSpecifications=[
                {
                    "ResourceType": "instance",
                    "Tags": [
                        {"Key": "Name", "Value": f"aws-experiment-{region}"}
                    ],
                }
            ],
        )
        instance = response["Instances"][0]
        instances.append({"InstanceId": instance["InstanceId"], "Region": region})


def wait_for_instances():
    """
    Waits until all instances are running and retrieves their public IPs.
    """
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


def test_connectivity(public_ips):
    """
    Tests connectivity between the instances by pinging each pair.
    """
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


def deploy_monitoring_script(public_ips):
    """
    Deploys a monitoring script to each instance to log resource utilization.
    """
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

    for ip in instances:
        try:
            print(f"Connecting to {ip}...")
            ssh.connect(hostname=ip, username="ubuntu", key_filename=f"keys/my_aws_key_{instances["Region"]}.pem")
            stdin, stdout, stderr = ssh.exec_command(f"echo '{monitoring_script}' > /tmp/monitor.sh && chmod +x /tmp/monitor.sh && /tmp/monitor.sh")
            print(stdout.read().decode(), stderr.read().decode())
        except Exception as e:
            print(f"Failed to connect to {ip}: {e}")

    ssh.close()


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
