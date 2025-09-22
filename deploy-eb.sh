#!/bin/bash

# EB Deployment script
echo "🚀 Deploying TripPlanner to AWS Elastic Beanstalk"

# Build frontend first
echo "🔨 Building frontend for production..."
cd trip_ui
npm ci
npm run build
cd ..

# Check if build was successful
if [ ! -d "trip_ui/dist" ]; then
    echo "❌ Frontend build failed. Deployment aborted."
    exit 1
fi

echo "✅ Frontend built successfully!"

# Check if EB CLI is installed
if ! command -v eb &> /dev/null; then
    echo "❌ EB CLI not found. Please install it first:"
    echo "pip install awsebcli"
    exit 1
fi

# Deploy to EB
echo "🐳 Deploying to Elastic Beanstalk..."
eb deploy

if [ $? -eq 0 ]; then
    echo "✅ Deployment successful!"
    echo "🌐 Your application is now live on AWS Elastic Beanstalk."
    echo "🔗 URL: $(eb status | grep 'CNAME' | awk '{print $2}')"
else
    echo "❌ Deployment failed!"
    exit 1
fi
