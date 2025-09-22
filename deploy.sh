#!/bin/bash

# Deployment script for AWS Elastic Beanstalk
echo "Starting deployment to AWS Elastic Beanstalk..."

# Build the frontend first
echo "Building frontend..."
./build_frontend.sh

if [ $? -ne 0 ]; then
    echo "Frontend build failed. Deployment aborted."
    exit 1
fi

# Check if EB CLI is installed
if ! command -v eb &> /dev/null; then
    echo "EB CLI not found. Please install it first:"
    echo "pip install awsebcli"
    exit 1
fi

# Initialize EB if not already done
if [ ! -f ".elasticbeanstalk/config.yml" ]; then
    echo "Initializing Elastic Beanstalk..."
    eb init
fi

# Deploy to EB
echo "Deploying to Elastic Beanstalk..."
eb deploy

if [ $? -eq 0 ]; then
    echo "Deployment successful!"
    echo "Your application is now live on AWS Elastic Beanstalk."
else
    echo "Deployment failed!"
    exit 1
fi

