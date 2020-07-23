#!/bin/bash

GAMING_INSTANCE_NAME="moge-gaming-rig"
LAUNCH_TEMPLATE_ID="lt-03fdabb49553e73e8"
LAUNCH_TEMPLATE_VERSION="3"

echo "aws ec2 describe-images --filters Name=name,Values="$GAMING_INSTANCE_NAME" --output text --query 'Images[*].{ID:ImageId}'"
ami=$(aws ec2 describe-images --filters Name=name,Values="$GAMING_INSTANCE_NAME" --output text --query 'Images[*].{ID:ImageId}')

echo "Will Launch new instance with AMI id: $ami"
echo "aws ec2 run-instances \
      --launch-template LaunchTemplateId=$LAUNCH_TEMPLATE_ID,Version=$LAUNCH_TEMPLATE_VERSION --image-id $ami"

aws ec2 run-instances \
      --launch-template LaunchTemplateId=$LAUNCH_TEMPLATE_ID,Version=$LAUNCH_TEMPLATE_VERSION --image-id $ami
