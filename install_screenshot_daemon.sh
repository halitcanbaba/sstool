#!/bin/bash
# install_screenshot_daemon.sh

set -e

echo "🚀 Installing Screenshot Monitoring Daemon..."
echo "=============================================="

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "❌ This script should not be run as root"
   exit 1
fi

# Update system
echo "📦 Updating system packages..."
sudo apt-get update -y
sudo apt-get upgrade -y

# Install required packages
echo "📦 Installing system dependencies..."
sudo apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    xvfb \
    systemd

# Create screenshot user if it doesn't exist
if ! id "screenshot" &>/dev/null; then
    echo "👤 Creating screenshot user..."
    sudo useradd -r -s /bin/false -d /opt/screenshot-daemon screenshot
fi

# Create directories
echo "📁 Creating directories..."
sudo mkdir -p /opt/screenshot-daemon
sudo mkdir -p /var/screenshots
sudo mkdir -p /var/run

# Copy files
echo "📋 Copying files..."
sudo cp screenshot_cron.py /opt/screenshot-daemon/
sudo cp screenshot-daemon.service /etc/systemd/system/
sudo cp requirements.txt /opt/screenshot-daemon/

# Set permissions
echo "🔐 Setting permissions..."
sudo chown -R screenshot:screenshot /opt/screenshot-daemon
sudo chown -R screenshot:screenshot /var/screenshots
sudo chmod +x /opt/screenshot-daemon/screenshot_cron.py
sudo chmod 644 /etc/systemd/system/screenshot-daemon.service

# Create Python virtual environment
echo "🐍 Setting up Python environment..."
sudo -u screenshot python3 -m venv /opt/screenshot-daemon/venv
sudo -u screenshot /opt/screenshot-daemon/venv/bin/pip install --upgrade pip
sudo -u screenshot /opt/screenshot-daemon/venv/bin/pip install -r /opt/screenshot-daemon/requirements.txt

# Update service file to use virtual environment
sudo sed -i 's|/usr/bin/python3|/opt/screenshot-daemon/venv/bin/python3|g' /etc/systemd/system/screenshot-daemon.service

# Reload systemd
echo "🔄 Reloading systemd..."
sudo systemctl daemon-reload

# Enable service
echo "✅ Enabling screenshot daemon service..."
sudo systemctl enable screenshot-daemon

# Create monitoring script
echo "📊 Creating monitoring script..."
cat > /tmp/screenshot-monitor.sh << 'EOF'
#!/bin/bash
# Screenshot Daemon Monitor

case "$1" in
    start)
        echo "🚀 Starting screenshot daemon..."
        sudo systemctl start screenshot-daemon
        ;;
    stop)
        echo "🛑 Stopping screenshot daemon..."
        sudo systemctl stop screenshot-daemon
        ;;
    restart)
        echo "🔄 Restarting screenshot daemon..."
        sudo systemctl restart screenshot-daemon
        ;;
    status)
        echo "📊 Screenshot daemon status:"
        sudo systemctl status screenshot-daemon --no-pager
        echo ""
        echo "📁 Recent screenshots:"
        ls -la /var/screenshots/screenshot_*.png 2>/dev/null | tail -5 || echo "No screenshots found"
        ;;
    logs)
        echo "📋 Screenshot daemon logs:"
        sudo journalctl -u screenshot-daemon -f
        ;;
    monitor)
        echo "📊 Interactive monitoring mode..."
        sudo -u screenshot /opt/screenshot-daemon/venv/bin/python3 /opt/screenshot-daemon/screenshot_cron.py monitor
        ;;
    test)
        echo "🧪 Testing single screenshot..."
        sudo -u screenshot xvfb-run -a /opt/screenshot-daemon/venv/bin/python3 /opt/screenshot-daemon/screenshot_cron.py single
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs|monitor|test}"
        exit 1
        ;;
esac
EOF

sudo mv /tmp/screenshot-monitor.sh /usr/local/bin/screenshot-monitor
sudo chmod +x /usr/local/bin/screenshot-monitor

echo ""
echo "✅ Installation completed successfully!"
echo ""
echo "🔧 Configuration:"
echo "   • Service file: /etc/systemd/system/screenshot-daemon.service"
echo "   • Script location: /opt/screenshot-daemon/screenshot_cron.py"
echo "   • Screenshots: /var/screenshots/"
echo "   • User: screenshot"
echo ""
echo "📝 Usage:"
echo "   • Start daemon: screenshot-monitor start"
echo "   • Stop daemon: screenshot-monitor stop"
echo "   • Check status: screenshot-monitor status"
echo "   • View logs: screenshot-monitor logs"
echo "   • Monitor mode: screenshot-monitor monitor"
echo "   • Test single screenshot: screenshot-monitor test"
echo ""
echo "🚀 To start the service now:"
echo "   screenshot-monitor start"
echo ""
echo "💡 To customize configuration, edit:"
echo "   sudo nano /opt/screenshot-daemon/screenshot_cron.py"
echo ""
echo "📚 For more information, check the logs:"
echo "   sudo journalctl -u screenshot-daemon -f"
