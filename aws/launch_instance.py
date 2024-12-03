import boto3

# Parameters for instance creation

REGION_NAME = 'eu-west-2'

# EU WEST 1
'''
REGION_NAME = 'eu-west-1'
AMI_ID = "ami-0d64bb532e0502c46"  # Replace with the correct AMI ID for your region
INSTANCE_TYPE = "t2.micro"  # Free-tier eligible instance type
SUBNET_ID = "subnet-0dfabf5b6c47eb240"  # Replace with your new subnet ID
KEY_NAME = "my_aws_key_eu-west-1"  # Replace with your key pair name
SECURITY_GROUP_ID = "sg-0837568cd61c41bbf"  # Replace with your security group ID
'''

# EU WEST 2
#'''
REGION_NAME = 'eu-west-2'
AMI_ID = "ami-0e8d228ad90af673b" # Replace with the correct AMI ID for your region
INSTANCE_TYPE = "t2.micro"  # Free-tier eligible instance type
SUBNET_ID = "subnet-0e14a14e8d2948184" #"subnet-0dfabf5b6c47eb240"  # Replace with your new subnet ID
KEY_NAME = "my_aws_key_eu-west-2" # Replace with your key pair name
SECURITY_GROUP_ID = "sg-04638beba3be30caf" # Replace with your security group ID
#'''

# Initialize a session using your credentials
session = boto3.Session(profile_name='default', region_name=REGION_NAME)  # Specify the region here
ec2 = session.resource('ec2')

# Create the EC2 instance
instance = ec2.create_instances(
    ImageId=AMI_ID,
    InstanceType=INSTANCE_TYPE,
    MaxCount=1,
    MinCount=1,
    KeyName=KEY_NAME,
    SubnetId=SUBNET_ID,
    SecurityGroupIds=[SECURITY_GROUP_ID],
    TagSpecifications=[
        {
            'ResourceType': 'instance',
            'Tags': [{'Key': 'Name', 'Value': 'MyFirstPublicInstance_'+REGION_NAME}],
        }
    ],
)

print(f"Instance {instance[0].id} is launching...")
print("Done")
