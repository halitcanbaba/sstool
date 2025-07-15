# Screenshot Monitoring Daemon for Linux Servers

A production-ready Python daemon for continuous screenshot monitoring on Ubuntu/Debian servers. Runs as a systemd service with comprehensive monitoring, health checks, and automatic cleanup.

## Features

- ✅ **Continuous screenshot monitoring** - Takes screenshots at configurable intervals
- ✅ **Multiple regions support** - Capture different screen areas simultaneously
- ✅ **Web page screenshots** - Capture screenshots of web pages using headless browser
- ✅ **Telegram integration** - Send screenshots to different Telegram groups per region
- ✅ **Daemon service** - Runs as a systemd service with automatic startup
- ✅ **Health monitoring** - Built-in health checks and system monitoring
- ✅ **Interactive monitoring** - Real-time status display
- ✅ **Automatic cleanup** - Removes old screenshots based on age and count
- ✅ **Headless operation** - Uses `xvfb` for server environments
- ✅ **Comprehensive logging** - Detailed logs with rotation
- ✅ **Resource monitoring** - Disk space and system resource checks
- ✅ **Signal handling** - Graceful shutdown and restart

## Requirements

- Ubuntu/Debian server
- Python 3.6+
- `pyautogui`, `Pillow`, `requests`, `selenium`, and `webdriver-manager` libraries
- `xvfb` for headless operation
- `firefox` for web screenshots
- `systemd` for service management
- Telegram bot (optional, for notifications)

## Quick Installation

```bash
# Clone or download the files
git clone <repository> screenshot-daemon
cd screenshot-daemon

# Run the installation script
chmod +x install_screenshot_daemon.sh
./install_screenshot_daemon.sh

# Start the service
screenshot-monitor start
```

## Manual Installation

```bash
# Install system dependencies
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv xvfb systemd

# Create user and directories
sudo useradd -r -s /bin/false -d /opt/screenshot-daemon screenshot
sudo mkdir -p /opt/screenshot-daemon /var/screenshots

# Copy files
sudo cp screenshot_cron.py /opt/screenshot-daemon/
sudo cp screenshot-daemon.service /etc/systemd/system/
sudo cp requirements.txt /opt/screenshot-daemon/

# Set permissions
sudo chown -R screenshot:screenshot /opt/screenshot-daemon /var/screenshots
sudo chmod +x /opt/screenshot-daemon/screenshot_cron.py

# Install Python dependencies
sudo -u screenshot python3 -m venv /opt/screenshot-daemon/venv
sudo -u screenshot /opt/screenshot-daemon/venv/bin/pip install -r /opt/screenshot-daemon/requirements.txt

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable screenshot-daemon
sudo systemctl start screenshot-daemon
```

## Configuration

Edit `/opt/screenshot-daemon/screenshot_cron.py` to customize:

```python
CONFIG = {
    "output_dir": "/var/screenshots",
    "regions": {
        "full_screen": None,  # Full screen
        "top_left": (0, 0, 960, 540),
        "top_right": (960, 0, 960, 540),
        "center": (480, 270, 960, 540),
        # ... more regions
    },
    "active_regions": ["full_screen"],  # Which regions to capture
    "interval": 60,  # seconds between screenshots
    "telegram": {
        "enabled": True,
        "bot_token": "YOUR_BOT_TOKEN",
        "region_chats": {
            "full_screen": "-1001234567890",
            "top_left": "-1001234567891",
            # ... more chat mappings
        }
    }
}
```

### Telegram Integration

Each region can send screenshots to different Telegram groups:

1. **Create Telegram Bot**: Visit @BotFather
2. **Setup Groups**: Create groups for each region
3. **Get Chat IDs**: Use @userinfobot to get group IDs
4. **Configure**: Update `region_chats` in config
5. **Test**: Use `python3 screenshot_cron.py telegram --test-telegram`

For detailed Telegram setup, see [TELEGRAM_SETUP.md](TELEGRAM_SETUP.md).

## Usage

### Service Management

```bash
# Start the daemon
screenshot-monitor start

# Stop the daemon
screenshot-monitor stop

# Restart the daemon
screenshot-monitor restart

# Check status
screenshot-monitor status

# View logs
screenshot-monitor logs

# Interactive monitoring
screenshot-monitor monitor

# Test single screenshot
screenshot-monitor test
```

### Direct Script Usage

```bash
# Start daemon
python3 screenshot_cron.py start

# Stop daemon
python3 screenshot_cron.py stop

# Check status
python3 screenshot_cron.py status

# Interactive monitoring
python3 screenshot_cron.py monitor

# Single screenshot
python3 screenshot_cron.py single

# Show configuration
python3 screenshot_cron.py config

# Test web screenshot functionality
python3 screenshot_cron.py web-test
```

### Web Screenshot Configuration

Configure web pages to capture in the main script:

```python
"web_screenshots": {
    "enabled": True,
    "browser": "firefox",  # 'firefox' or 'chrome'
    "headless": True,
    "window_size": (1920, 1080),
    "urls": {
        "google": {
            "url": "https://www.google.com",
            "wait_time": 3,
            "element_selector": None,
            "telegram_chat_id": "-1002745524480"
        },
        "github": {
            "url": "https://github.com",
            "wait_time": 5,
            "element_selector": ".Header",
            "telegram_chat_id": "-1002745524480"
        }
    },
    "active_urls": ["google", "github"],
    "interval": 300,  # 5 minutes
    "delete_after_send": True
}
```

### Command Line Options

```bash
# Custom interval (30 seconds)
python3 screenshot_cron.py start --interval 30

# Custom region
python3 screenshot_cron.py start --region "0,0,1920,1080"

# Custom output directory
python3 screenshot_cron.py start --output "/home/user/screenshots"
```

## Health Monitoring

The daemon includes built-in health monitoring:

```bash
# Run health check
python3 health_monitor.py

# Continuous monitoring
python3 health_monitor.py --continuous

# Custom interval (check every 60 seconds)
python3 health_monitor.py --continuous --interval 60
```

### Health Check Features

- ✅ **Recent Screenshots** - Ensures screenshots are being taken
- ✅ **Disk Space** - Monitors available disk space
- ✅ **Process Status** - Checks if daemon is running
- ✅ **File Size Validation** - Ensures screenshots are valid
- ✅ **Email Alerts** - Optional email notifications

## Monitoring Dashboard

The interactive monitoring mode provides real-time status:

```bash
screenshot-monitor monitor
```

Shows:
- Service status and uptime
- Screenshot statistics
- Recent files
- Error counts
- System resources

## File Structure

```
/opt/screenshot-daemon/
├── screenshot_cron.py          # Main daemon script
├── venv/                       # Python virtual environment
└── requirements.txt            # Python dependencies

/var/screenshots/
├── screenshot_2025-07-14_22-00-00.png
├── screenshot_2025-07-14_22-01-00.png
├── screenshot_daemon.log       # Daemon logs
└── ...

/etc/systemd/system/
└── screenshot-daemon.service   # Systemd service file
```

## Logging

Comprehensive logging in `/var/screenshots/screenshot_daemon.log`:

```
2025-07-14 22:00:01,234 [INFO] Screenshot daemon started
2025-07-14 22:00:01,235 [INFO] Taking screenshot of region: (100, 100, 800, 600)
2025-07-14 22:00:01,456 [INFO] Screenshot saved: screenshot_2025-07-14_22-00-01.png (245760 bytes)
2025-07-14 22:05:01,234 [INFO] Health check passed
2025-07-14 22:10:01,234 [INFO] Cleaned up 5 old screenshots
```

## Systemd Integration

The daemon integrates with systemd for:

- **Automatic startup** on boot
- **Automatic restart** on failure
- **Journal logging** with `journalctl`
- **Resource management** and security
- **Signal handling** for graceful shutdown

```bash
# View service logs
sudo journalctl -u screenshot-daemon -f

# Check service status
sudo systemctl status screenshot-daemon

# Enable auto-start
sudo systemctl enable screenshot-daemon
```

## Security Features

- **Dedicated user** - Runs as non-privileged `screenshot` user
- **Restricted permissions** - Limited file system access
- **Private tmp** - Isolated temporary directory
- **No new privileges** - Prevents privilege escalation
- **Protected system** - Read-only system directories

## Troubleshooting

### Common Issues

1. **Service won't start**
   ```bash
   sudo journalctl -u screenshot-daemon -n 50
   ```

2. **No screenshots being taken**
   ```bash
   screenshot-monitor test
   python3 health_monitor.py
   ```

3. **Permission denied**
   ```bash
   sudo chown -R screenshot:screenshot /var/screenshots
   ```

4. **Disk space issues**
   ```bash
   # Check disk usage
   df -h /var/screenshots
   
   # Manual cleanup
   sudo find /var/screenshots -name "screenshot_*.png" -mtime +7 -delete
   ```

### Debugging

```bash
# Debug mode
sudo -u screenshot /opt/screenshot-daemon/venv/bin/python3 /opt/screenshot-daemon/screenshot_cron.py start

# Check configuration
python3 screenshot_cron.py config

# Test without daemon
python3 screenshot_cron.py single
```

## Performance Considerations

- **Interval tuning** - Adjust based on requirements
- **Disk space** - Monitor and set appropriate cleanup policies
- **CPU usage** - Screenshot taking uses CPU resources
- **Memory usage** - Image processing requires memory
- **Network** - Consider bandwidth for remote storage

## Advanced Configuration

### Email Alerts

Edit `health_monitor.py` configuration:

```python
MONITOR_CONFIG = {
    "email_alerts": True,
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "email_from": "alerts@yourserver.com",
    "email_to": "admin@yourserver.com",
    "email_password": "your_app_password"
}
```

### Custom Regions

```python
# Full screen
"region": (0, 0, 1920, 1080)

# Specific application window
"region": (100, 100, 800, 600)

# Multiple monitors - use pyautogui.screenshot() without region
```

### Log Rotation

Add to `/etc/logrotate.d/screenshot-daemon`:

```
/var/screenshots/screenshot_daemon.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 screenshot screenshot
    postrotate
        systemctl reload screenshot-daemon
    endscript
}
```

## Backup and Recovery

```bash
# Backup screenshots
tar -czf screenshots_backup_$(date +%Y%m%d).tar.gz /var/screenshots

# Restore service
sudo systemctl stop screenshot-daemon
sudo cp screenshot_cron.py /opt/screenshot-daemon/
sudo systemctl start screenshot-daemon
```

## License

This project is provided as-is for educational and production use.

## Support

For issues and questions:
1. Check the logs: `sudo journalctl -u screenshot-daemon -f`
2. Run health check: `python3 health_monitor.py`
3. Test single screenshot: `screenshot-monitor test`
