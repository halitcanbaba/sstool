#!/bin/bash

# Setup script for headless screenshot service on Ubuntu/Debian
# Run this script to install dependencies and set up the screenshot service

echo "Setting up headless screenshot service..."

# Update package list
sudo apt-get update

# Install required system packages
echo "Installing system dependencies..."
sudo apt-get install -y python3 python3-pip xvfb

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

# Create default screenshot directory
SCREENSHOT_DIR="/var/screenshots"
echo "Creating screenshot directory: $SCREENSHOT_DIR"
sudo mkdir -p $SCREENSHOT_DIR
sudo chown $USER:$USER $SCREENSHOT_DIR

# Make the script executable
chmod +x screenshot_cron.py

echo "Setup complete!"
echo ""
echo "To test the script manually:"
echo "  xvfb-run -a python3 $(pwd)/screenshot_cron.py"
echo ""
echo "To add to crontab (run every hour):"
echo "  0 * * * * xvfb-run -a python3 $(pwd)/screenshot_cron.py"
echo ""
echo "To edit crontab:"
echo "  crontab -e"
echo ""
echo "Remember to:"
echo "1. Edit the OUTPUT_DIR and REGION variables in screenshot_cron.py"
echo "2. Test the script before adding to cron"
echo "3. Check logs in the output directory"
