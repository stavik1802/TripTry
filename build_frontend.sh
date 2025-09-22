#!/bin/bash

# Build script for frontend deployment
echo "Building frontend for production..."

# Navigate to frontend directory
cd trip_ui

# Install dependencies
echo "Installing frontend dependencies..."
npm ci

# Build the frontend
echo "Building frontend..."
npm run build

# Check if build was successful
if [ $? -eq 0 ]; then
    echo "Frontend build completed successfully!"
    echo "Built files are in trip_ui/dist/"
else
    echo "Frontend build failed!"
    exit 1
fi

# Go back to root directory
cd ..


