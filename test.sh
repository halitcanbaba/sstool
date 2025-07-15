#!/bin/bash

# Test script to verify the screenshot setup

echo "Testing headless screenshot setup..."
echo "=================================="

# Check if required commands exist
echo "Checking system requirements..."

if ! command -v python3 &> /dev/null; then
    echo "❌ python3 not found"
    exit 1
fi
echo "✅ python3 found"

if ! command -v xvfb-run &> /dev/null; then
    echo "❌ xvfb-run not found - install with: sudo apt-get install xvfb"
    exit 1
fi
echo "✅ xvfb-run found"

# Check Python dependencies
echo ""
echo "Checking Python dependencies..."

if ! python3 -c "import pyautogui" &> /dev/null; then
    echo "❌ pyautogui not found - install with: pip3 install pyautogui"
    exit 1
fi
echo "✅ pyautogui found"

if ! python3 -c "import PIL" &> /dev/null; then
    echo "❌ Pillow not found - install with: pip3 install Pillow"
    exit 1
fi
echo "✅ Pillow found"

# Test screenshot functionality
echo ""
echo "Testing screenshot functionality..."

if xvfb-run -a python3 screenshot_cron.py; then
    echo "✅ Screenshot test successful"
    
    # Check if screenshot was created
    if ls /var/screenshots/screenshot_*.png &> /dev/null; then
        echo "✅ Screenshot file created"
        latest_screenshot=$(ls -t /var/screenshots/screenshot_*.png | head -1)
        echo "📸 Latest screenshot: $latest_screenshot"
        
        # Show file info
        file_size=$(stat -c%s "$latest_screenshot" 2>/dev/null || stat -f%z "$latest_screenshot" 2>/dev/null)
        echo "📁 File size: $file_size bytes"
    else
        echo "❌ No screenshot file found"
    fi
else
    echo "❌ Screenshot test failed"
    exit 1
fi

echo ""
echo "✅ All tests passed!"
echo ""
echo "Example crontab entries:"
echo "# Every hour:"
echo "0 * * * * xvfb-run -a python3 $(pwd)/screenshot_cron.py"
echo ""
echo "# Every 30 minutes:"
echo "*/30 * * * * xvfb-run -a python3 $(pwd)/screenshot_cron.py"
echo ""
echo "Add to crontab with: crontab -e"
