"""
Salt module for Amazon EC2 instance

:configuration: This module accepts only IAM roles assigned to 
    the instance through Instance Profiles. Dynamic credentials are then automatically 
    obtained from AWS API and no further
    configuration is necessary. More Information available at:
    .. code-block:: text

        http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html

    If IAM roles are not used you need to specify them either in a pillar or
    in the minion's config file:

"""

import boto3
import time
from botocore.exceptions import ClientError
from botocore.config import Config
from botocore.credentials import InstanceMetadataProvider, InstanceMetadataFetcher

def restart_ec2_by_private_ip(private_ip, region):

        provider = InstanceMetadataProvider(iam_role_fetcher=InstanceMetadataFetcher(timeout=1000, num_attempts=2))
        creds = provider.load().get_frozen_credentials()
        ec2 = boto3.client('ec2', region_name=region,aws_access_key_id=creds.access_key, aws_secret_access_key=creds.secret_key, aws_session_token=creds.token)

        response = ec2.describe_instances(Filters=[{'Name': 'private-ip-address', 'Values': [private_ip]}])
        print(response)
        instance_id = response['Reservations'][0]['Instances'][0]['InstanceId']

        response = ec2.describe_instance_status(InstanceIds=[instance_id], IncludeAllInstances=True)
        
        instance_status = response['InstanceStatuses'][0]['InstanceState']['Name']
        if instance_status != "running":
            try:
                if instance_status == "stopped":
                    ec2.start_instances(InstanceIds=[instance_id])
                    return response['ResponseMetadata']['HTTPStatusCode'] == 200
                elif instance_status in ["stopping", "shutting-down"]:
                    retry = 0
                    while retry < 5:
                        print(f"Instance still in {status}, retrying again in 60secs.")
                        time.sleep(60)
                        status = check_instance_status(ec2, instance_id)
                        if status == "stopped":
                            ec2.start_instances(InstanceIds=[instance_id])
                            return response['ResponseMetadata']['HTTPStatusCode'] == 200
                        else:
                            print(f"Instance still in {status}, retrying again in 60secs.")
                            retry += 1
                    raise Exception("Couldn't start the instance after 5 retries.")
                else:
                    raise Exception(f"Instance not in a state to start/reboot, status: {status}.")

            except Exception as e:
                raise Exception("Instance failed to start/reboot, please check.")
        else:
            raise Exception("Instance is already in running state, please check.")

def check_instance_status(ec2, instance_id):
    try:
        response = ec2.describe_instance_status(InstanceIds=[instance_id], IncludeAllInstances=True)
        instance_status = response['InstanceStatuses'][0]['InstanceState']['Name']
        print(instance_status)
        return instance_status

    except Exception as e:
        return str(e)
