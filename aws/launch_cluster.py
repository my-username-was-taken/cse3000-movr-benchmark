import boto3
import os
import sys
import time
import json
import argparse
import paramiko
import subprocess

# Global variables
instances = []

# Helper functions
def load_config(config_file):
    """
    Load configuration from the JSON file.
    """
    with open(config_file, "r") as f:
        return json.load(f)

def execute_remote_command(ssh_client, command):
    """
    Execute a command on a remote server over SSH.
    """
    stdin, stdout, stderr = ssh_client.exec_command(command)
    print(stdout.read().decode())
    print(stderr.read().decode())

# Load configuration
with open("aws/aws.json", "r") as f:
    config = json.load(f)

AWS_USERNAME = config["aws_username"]
REGIONS = config["regions"]
VM_TYPE = config["vm_type"]
AMI_IDS = config["regions"]  # Contains AMI and Subnet for each region
KEY_FOLDER = "keys"

instances = []

# Initialize AWS clients for each region
ec2_clients = {region: boto3.client("ec2", region_name=region) for region in REGIONS.keys()}

# Initialize ec2 Sessions
ec2_sessions = {region: boto3.Session(profile_name='default', region_name=region).resource('ec2') for region in REGIONS.keys()}

def ensure_key_pair(region, key_folder):
    """
    Ensures a key pair named 'my_aws_key_<region>' exists in the specified region.
    If it doesn't exist, creates it and saves the private key in the keys folder.
    """
    key_name = f"my_aws_key_{region}"
    client = boto3.client("ec2", region_name=region)
    private_key_file = os.path.join(key_folder, f"{key_name}.pem")

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

            # Save the private key to the keys folder
            os.makedirs(key_folder, exist_ok=True)
            with open(private_key_file, "w") as f:
                f.write(key_material)
            os.chmod(private_key_file, 0o400)
            print(f"Key pair '{key_name}' created. Private key saved to '{private_key_file}'.")
        else:
            raise
    return key_name


def launch_instances(config, key_folder):
    """
    Launches one EC2 instance in each region specified in the configuration.
    """
    for region, client in ec2_clients.items():
        region_config = REGIONS[region]
        ensure_key_pair(region, key_folder)  # Ensure the key pair exists
        key_name = f"my_aws_key_{region}"

        print(f"Launching instance in {region}...")
        #ec2_client = ec2_clients[region]
        ec2_session = ec2_sessions[region]
        instance = ec2_session.create_instances(
            ImageId=region_config["ami_id"],
            InstanceType=config["vm_type"],
            KeyName=key_name,
            MaxCount=1,
            MinCount=1,
            SubnetId=region_config["subnet_id"],
            SecurityGroupIds=[region_config["sg_id"]],
            TagSpecifications=[
                {
                    'ResourceType': 'instance',
                    'Tags': [{'Key': 'Name', 'Value': 'MyFirstPublicInstance_'+region}],
                }
            ],
        )
        instances.append({"InstanceId": instance[0].id, "Region": region})


def wait_for_instances():
    """
    Waits until all instances are running and retrieves their public IPs.
    """
    public_ips = []
    region_ips = {}
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
        region_ips[region] = {"ip": public_ip, "instance_id": instance_id}
    
    with open('aws/ips.json', 'w') as fp:
        json.dump(region_ips, fp)

    return public_ips


def setup_vm(public_ip, key_path, github_credentials):
    """
    Clone the repository and execute the setup script on a remote VM.
    """
    print(f"Setting up VM at {public_ip}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(hostname=public_ip, username="ubuntu", key_filename=key_path)

        # Transfer GitHub credentials
        sftp = ssh.open_sftp()
        sftp.put("aws/github_credentials.json", "/home/ubuntu/github_credentials.json")
        sftp.close()
        print("GitHub credentials transferred.")

        # Clone the repository
        clone_command = """
        export GIT_ASKPASS=/bin/echo &&
        echo {} > /tmp/token &&
        git clone https://{}:{}@github.com/delftdata/Detock.git
        """.format(github_credentials["token"], github_credentials["username"], github_credentials["token"])
        execute_remote_command(ssh, clone_command)
        print("Repository cloned.")

        # Run the setup script
        setup_command = "bash /home/ubuntu/Detock/aws/setup.sh"
        execute_remote_command(ssh, setup_command)
        print("Setup script executed.")

    except Exception as e:
        print(f"Error setting up VM {public_ip}: {e}")
    finally:
        ssh.close()


def setup_vms(public_ips):
    # Load GitHub credentials
    with open("aws/github_credentials.json", "r") as f:
        github_credentials = json.load(f)

    # Set up each VM
    for ip in public_ips:
        key_path = os.path.join(KEY_FOLDER, f"my_aws_key_{region}.pem")
        setup_vm(ip, key_path, github_credentials)


def stop_cluster():
    """
    Terminates all instances launched during this session.
    """
    with open('aws/ips.json') as file:
        region_ips = json.load(file)

    for region in region_ips.keys():
        instance_id = region_ips[region]["instance_id"]

        print(f"Terminating instance {instance_id} in {region}...")
        ec2_clients[region].terminate_instances(InstanceIds=[instance_id])
        print(f"Instance {instance_id} in {region} terminated.")


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
            ssh.connect(hostname=ip, username="ubuntu", key_filename=f"keys/my_aws_key_eu-west-1.pem")
            stdin, stdout, stderr = ssh.exec_command(f"echo '{monitoring_script}' > /tmp/monitor.sh && chmod +x /tmp/monitor.sh && /tmp/monitor.sh")
            print(stdout.read().decode(), stderr.read().decode())
        except Exception as e:
            print(f"Failed to connect to {ip}: {e}")

    ssh.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AWS Cluster Management Script")
    parser.add_argument("action", choices=["start", "stop"], help="Action to perform: start or stop the cluster.")
    parser.add_argument("-cfg", default="aws/aws.json", help="Path to the config file.")
    args = parser.parse_args()

    config_file = args.cfg
    config = load_config(config_file)

    if args.action == "start":
        launch_instances(config, KEY_FOLDER)
        public_ips = wait_for_instances()

        setup_vms(public_ips)

        # Ignore this step for now (does not work anyway)
        #test_connectivity(public_ips)
        # We want to use alternative monitoring script
        #deploy_monitoring_script(public_ips, KEY_FOLDER)
    elif args.action == "stop":
        stop_cluster()
