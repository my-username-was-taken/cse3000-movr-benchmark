import boto3
import os
import sys
import time
import json
import argparse
import paramiko
import subprocess as sp
import csv
from concurrent.futures import ThreadPoolExecutor

# Global variables
IPS_FILE = 'aws/ips.json'
YCSB_CONF_FILE = 'examples/aws_cluster_ycsb.conf'
TPCC_CONF_FILE = 'examples/aws_cluster_tpcc.conf'

LOGGING_FILE = 'aws/VM_launch_logging.log'

INSTANCES_PER_REGION = 4
server_instances = []
client_instances = []
all_instances = []

# Helper functions
def load_config(config_file):
    """
    Load configuration from the JSON file.
    """
    with open(config_file, "r") as f:
        return json.load(f)

def load_region_ips_from_file():
    with open(IPS_FILE) as file:
        region_ips = json.load(file)
    return region_ips

def execute_remote_command(ssh_client, command):
    """
    Execute a command on a remote server over SSH.
    """
    _, stdout, stderr = ssh_client.exec_command(command)
    print(stdout.read().decode())
    print(stderr.read().decode())

KEY_FOLDER = "keys"

instances = []

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
    for region, _ in ec2_clients.items():
        region_config = REGIONS[region]
        ensure_key_pair(region, key_folder)  # Ensure the key pair exists
        key_name = f"my_aws_key_{region}"

        print(f"Launching instances in {region}...")
        ec2_session = ec2_sessions[region]
        instances = ec2_session.create_instances(
            ImageId=region_config["ami_id"],
            InstanceType=config["vm_type"],
            KeyName=key_name,
            MaxCount=INSTANCES_PER_REGION+1, # Last instance is the client
            MinCount=INSTANCES_PER_REGION+1,
            SubnetId=region_config["subnet_id"],
            SecurityGroupIds=[region_config["sg_id"]],
            TagSpecifications=[
                {
                    'ResourceType': 'instance',
                    'Tags': [{'Key': 'Name', 'Value': f'DetockVM_{region}'}],
                }
            ],
        )
        # Rename instances in same region with index to distinuish between them
        for index, instance in enumerate(instances[:-1], start=1):
            unique_name = f'DetockVM_{region}_{index}'
            instance.create_tags(
                Tags=[{'Key': 'Name', 'Value': unique_name}]
            )
            server_instances.append({"InstanceId": instance.id, "Region": region, "Name": unique_name})
        
        # Special name for the client VMs
        client_name = f'ClientVM_{region}'
        instances[-1].create_tags(
            Tags=[{'Key': 'Name', 'Value': client_name}]
        )
        client_instances.append({"InstanceId": instances[-1].id, "Region": region, "Name": client_name})


def wait_for_instances(all_instances):
    """
    Waits until all instances are running and retrieves their public IPs.
    """
    public_ips = []
    region_ips = {}
    for region in REGIONS:
        region_ips[region] = []
    for instance in all_instances:
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
        region_ips[region].append({"ip": public_ip, "instance_id": instance_id, "server": 'DetockVM_' in instance["Name"]})
    
    with open(IPS_FILE, 'w') as fp:
        json.dump(region_ips, fp, indent=4)

    return public_ips, region_ips


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

        # Clone Detock repository
        clone_command = """
        export GIT_ASKPASS=/bin/echo &&
        echo {} > /tmp/token &&
        git clone https://{}:{}@github.com/delftdata/Detock.git
        """.format(github_credentials["token"], github_credentials["username"], github_credentials["token"])
        execute_remote_command(ssh, clone_command)
        print("Detock Repository cloned.")

        # Clone iftop repo
        # For now let's just estimate the average cost
        '''clone_command = """
        export GIT_ASKPASS=/bin/echo &&
        echo {} > /tmp/token &&
        git clone https://{}:{}@github.com/delftdata/iftop.git
        """.format(github_credentials["token"], github_credentials["username"], github_credentials["token"])
        execute_remote_command(ssh, clone_command)
        print("Iftop Repository cloned.")'''

        # Run the setup script
        setup_command = "bash /home/ubuntu/Detock/aws/setup.sh"
        execute_remote_command(ssh, setup_command)
        print("Setup script executed.")

    except Exception as e:
        print(f"Error setting up VM {public_ip}: {e}")
    finally:
        ssh.close()


def setup_vms(all_instances):
    # Load GitHub credentials
    with open("aws/github_credentials.json", "r") as f:
        github_credentials = json.load(f)

    def setup_task(instance):
        key_path = os.path.join(KEY_FOLDER, f"my_aws_key_{instance['Region']}.pem")
        setup_vm(instance["PublicIp"], key_path, github_credentials)

    # Setup all VMs concurrently
    with ThreadPoolExecutor() as executor:
        executor.map(setup_task, all_instances)


def stop_cluster():
    """
    Terminates all instances launched during this session.
    """
    region_ips = load_region_ips_from_file()

    for region in list(region_ips.keys()):
        region_instance_ids = []
        for region_instance in region_ips[region]:
            region_instance_ids.append(region_instance["instance_id"])

        print(f"Terminating instances {str(region_instance_ids)} in {region}...")
        ec2_clients[region].terminate_instances(InstanceIds=region_instance_ids)
        print(f"Instances {str(region_instance_ids)} in {region} terminated.")


def test_connectivity_between_regions(region_ips, username='ubuntu'):
    """
    Tests connectivity between instances in different regions by SSHing into them
    and pinging other instances. Saves the round-trip time (RTT) as a matrix CSV.
    
    Args:
        region_ips (dict): Dictionary of regions with instance public IPs and IDs.
        key_file (str): Path to the private key file for SSH.
        username (str): SSH username (e.g., "ubuntu").
    """
    print("Testing connectivity between VMs across regions...")

    # Prepare a blank RTT matrix with region names as headers
    regions = list(region_ips.keys())
    rtt_matrix = [[""] + regions]  # First row header

    for src_region in regions:
        # Just use the 1st VM in each region to test ping latencies
        src_ip = region_ips[src_region][0]["ip"]
        row = [src_region]  # First column header

        # SSH into the source instance
        try:
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client.connect(hostname=src_ip, username=username, key_filename=os.path.join(KEY_FOLDER, f"my_aws_key_{src_region}.pem"))
            print(f"Connected to {src_region} ({src_ip})")

            # Test connectivity to other instances
            for dest_region in regions:
                dest_ip = region_ips[dest_region][0]["ip"]
                if src_region == dest_region:
                    row.append("N/A")  # Skip self-connectivity
                else:
                    # Execute ping command on the remote VM
                    _, stdout, stderr = ssh_client.exec_command(f"ping -c 1 {dest_ip}")
                    ping_output = stdout.read().decode()
                    rtt_time = "N/A"
                    if "time=" in ping_output:
                        for line in ping_output.splitlines():
                            if "time=" in line:
                                rtt_time = line.split("time=")[1].split(" ")[0]  # Extract RTT
                                break
                    row.append(rtt_time)
                    print(f"RTT from {src_region} to {dest_region}: {rtt_time} ms")

            ssh_client.close()
        except Exception as e:
            print(f"Error connecting to {src_region} ({src_ip}): {e}")
            row += ["Error"] * len(regions)

        rtt_matrix.append(row)

    # Save RTT matrix as CSV
    output_file = "aws/rtt_matrix_regions.csv"
    with open(output_file, mode="w", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerows(rtt_matrix)
    print(f"RTT matrix saved to {output_file}")


def test_connectivity(public_ips):
    """
    Tests connectivity between the instances by pinging each pair.
    """
    print("Testing connectivity between VMs...")
    rtt_table = [["Origin", "Destination", "RTT (ms)"]]
    for src_ip in public_ips:
        for dest_ip in public_ips:
            if src_ip != dest_ip:
                rtt = sp.run(
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


def update_conf_file_ips():
    print(f"Updating IPs in .conf files")

    # 1. Collect IPs from JSON
    with open(IPS_FILE, "r") as f:
        ips_data = json.load(f)

    regions = list(ips_data)
    regions_ip_lines = []
    for region in regions:
        cur_ips = ips_data[region]

        client_address = ''
        server_addresses = []
        current_region_ip_lines = ['regions: {']
        for ip in cur_ips:
            if ip['server']:
                cur_ip = ip['ip']
                server_addresses.append(cur_ip)
                current_region_ip_lines.append(f'    addresses: "{cur_ip}",')
            else:
                client_address = ip['ip']
        # Here append the lines for the client and replicas (hard-coded at the moment)
        current_region_ip_lines.append(f'    client_addresses: "{client_address}",')
        current_region_ip_lines.append('    num_replicas: 1,')
        current_region_ip_lines.append('}')
        regions_ip_lines.extend(current_region_ip_lines)

    for conf in [YCSB_CONF_FILE, TPCC_CONF_FILE]:
        # 2. Populate .conf with IPs
        with open(conf) as file:
            conf_lines = [line.rstrip() for line in file]

        new_conf_file_lines = []
        addresses_section = False
        addresses_section_reached = False
        for line in conf_lines:
            if 'regions: {' in line:
                addresses_section = True
                if not addresses_section_reached:
                    new_conf_file_lines = new_conf_file_lines + regions_ip_lines
                addresses_section_reached = True
            else:
                if not addresses_section:
                    new_conf_file_lines.append(line)
                if addresses_section and '}' in line:
                    addresses_section = False

        # 3. Write new IPs back to file
        with open(conf, 'w') as f:
            for line in new_conf_file_lines:
                f.write(f"{line}\n")


def spawn_db_service(workload='YCSB', image='omraz/seq_eval:latest'):
    spawn_db_service_cmd = "python3.8 tools/admin.py start --image {} examples/{}.conf -u ubuntu -e GLOG_v=1"
    if workload == 'YCSB':
        print("Spawning YCSB-T DB service")
        conf_file = 'aws_cluster_ycsb'
        spawn_db_service_cmd = spawn_db_service_cmd.format(image, conf_file)
    elif workload == 'TPCC':
        print("Spawning YCSB-T DB service")
        conf_file = 'aws_cluster_tpcc'
        spawn_db_service_cmd = spawn_db_service_cmd.format(image, conf_file)
    else:
        print("Invalid workload selected")
    result = sp.run(spawn_db_service_cmd, shell=True, capture_output=True, text=True)
    if hasattr(result, "returncode") and result.returncode != 0:
        print(f"Spawning DB service failed with exit code {result.returncode}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AWS Cluster Management Script")
    parser.add_argument("-a", "--action", default="start", choices=["start", "status", "stop", "setup_db"], help="Action to perform: start or stop the cluster.")
    parser.add_argument("-cfg", default="aws/aws.json", help="Path to the config file.")
    parser.add_argument("-img", default="omraz/seq_eval:latest", help="Docker img to use.")
    args = parser.parse_args()

    config_file = args.cfg
    config = load_config(config_file)
    image = args.img
    AWS_USERNAME = config["aws_username"]
    REGIONS = config["regions"]
    VM_TYPE = config["vm_type"]
    AMI_IDS = config["regions"]  # Contains AMI and Subnet for each region

    # Initialize AWS clients for each region
    ec2_clients = {region: boto3.client("ec2", region_name=region) for region in REGIONS.keys()}

    # Initialize ec2 Sessions
    ec2_sessions = {region: boto3.Session(profile_name='default', region_name=region).resource('ec2') for region in REGIONS.keys()}

    if args.action == "start":
        launch_instances(config, KEY_FOLDER)
        all_instances += server_instances
        all_instances += client_instances
        public_ips, region_ips = wait_for_instances(all_instances)

        setup_vms(all_instances)
        test_connectivity_between_regions(region_ips)
    elif args.action == "status":
        region_ips = load_region_ips_from_file()
        public_ips = []
        for reg in region_ips.keys():
            for instance in region_ips[reg]:
                public_ips.append(instance["ip"])

        test_connectivity_between_regions(region_ips)
    elif args.action == "setup_db":
        update_conf_file_ips()
        # Will be handled by Python script inside machine
        #spawn_db_service(workload='YCSB', image=image)
    elif args.action == "stop":
        stop_cluster()
