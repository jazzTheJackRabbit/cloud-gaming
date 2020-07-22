import boto3
import botocore

SNAP_DELETE_TAG = 'SnapAndDelete'
GAMING_INSTANCE_NAME = 'moge-gaming-rig'
GAMING_INSTANCE_REGION = 'us-west-2'
GAMING_INSTANCE_SIZE_GB = 300


def lambda_handler(object, context):
    ec2 = boto3.client('ec2')

    # Connect to region
    ec2 = boto3.client('ec2', region_name=GAMING_INSTANCE_REGION)
    res_client = boto3.resource('ec2', region_name=GAMING_INSTANCE_REGION)

    def get_target_volumes():
        # Get all available volumes
        volumes = ec2.describe_volumes(Filters=[
            {'Name': 'tag:Name', 'Values': [GAMING_INSTANCE_NAME]},
            {'Name': 'status', 'Values': ['available']}
        ])['Volumes']

        # Get all volumes for the given instance
        volumes_to_delete = []
        for volume in volumes:
            for tag in volume['Tags']:
                if tag['Key'] == 'Name' and tag['Value'] == GAMING_INSTANCE_NAME:
                    volumes_to_delete.append(volume)

        if len(volumes_to_delete) == 0:
            print('No volumes found. Nothing to do! Aborting...')
            return None

        return volumes_to_delete

    def create_volume_snapshot(volumes_to_delete):
        # Create a snapshot of the volumes
        created_snapshot_ids = []
        for volume in volumes_to_delete:
            snap = ec2.create_snapshot(VolumeId=volume['VolumeId'])
            snap_id = snap['SnapshotId']
            snap_waiter = ec2.get_waiter('snapshot_completed')

            try:
                snap_waiter.wait(SnapshotIds=[snap_id], WaiterConfig={'Delay': 15, 'MaxAttempts': 59})
            except botocore.exceptions.WaiterError as e:
                print("Could not create snapshot, aborting")
                print(e.message)
                return

            print("Created snapshot: {}".format(snap['SnapshotId']))
            created_snapshot_ids.append(snap['SnapshotId'])

        # Tag the snapshots
        if len(created_snapshot_ids) > 0:
            ec2.create_tags(
                Resources=created_snapshot_ids,
                Tags=[
                    {'Key': 'SnapAndDelete', 'Value': 'True'},
                    {'Key': 'Name', 'Value': "Snapshot of " + GAMING_INSTANCE_NAME}
                ]
            )

        return created_snapshot_ids

    def delete_previous_volume_snapshots(snaps_created):
        # Remove previous snapshots of the volumes
        previous_snapshots = ec2.describe_snapshots(
            Filters=[{'Name': 'tag-key', 'Values': ['SnapAndDelete']}]
        )['Snapshots']

        for snapshot in previous_snapshots:
            if snapshot['SnapshotId'] not in snaps_created:
                print("Removing previous snapshot: {}".format(snapshot['SnapshotId']))
                ec2.delete_snapshot(SnapshotId=snapshot['SnapshotId'])

    def delete_volumes(volumes_to_delete):
        # Delete the volumes
        for volume in volumes_to_delete:
            v = res_client.Volume(volume['VolumeId'])
            print("Deleting EBS volume: {}, Size: {} GiB".format(v.id, v.size))
            v.delete()

    def delete_amis():
        # Delete any current AMIs
        images = ec2.describe_images(Owners=['self'])['Images']
        for ami in images:
            if ami['Name'] == GAMING_INSTANCE_NAME:
                print('Deleting image {}'.format(ami['ImageId']))
                ec2.deregister_image(DryRun=False, ImageId=ami['ImageId'])

    def create_new_ami(snaps_created):
        # Create a new AMI
        if len(snaps_created) > 0:
            amis_created = []
            ami = ec2.register_image(
                Name=GAMING_INSTANCE_NAME,
                Description=GAMING_INSTANCE_NAME + ' Automatic AMI',
                BlockDeviceMappings=[
                    {
                        'DeviceName': '/dev/sda1',
                        'Ebs': {
                            'DeleteOnTermination': False,
                            'SnapshotId': snaps_created[0],
                            'VolumeSize': GAMING_INSTANCE_SIZE_GB,
                            'VolumeType': 'gp2'
                        }
                    },
                ],
                Architecture='x86_64',
                RootDeviceName='/dev/sda1',
                DryRun=False,
                VirtualizationType='hvm',
                SriovNetSupport='simple'
            )
            print('Created image {}'.format(ami['ImageId']))
            amis_created.append(ami['ImageId'])

            if len(amis_created) > 0:
                # Tag the AMI
                ec2.create_tags(
                    Resources=amis_created,
                    Tags=[
                        {'Key': 'SnapAndDelete', 'Value': 'True'},
                        {'Key': 'Name', 'Value': GAMING_INSTANCE_NAME}
                    ]
                )

    volumes_to_delete = get_target_volumes()

    snaps_created = create_volume_snapshot(volumes_to_delete)

    # Delete any current AMIs
    delete_amis()

    # Create new AMIs
    create_new_ami(snaps_created)

    # Delete the volumes-snapshot
    delete_previous_volume_snapshots(snaps_created)

    # Delete the volumes
    delete_volumes(volumes_to_delete)
