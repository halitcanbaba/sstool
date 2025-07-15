#!/usr/bin/env python3
"""
Screenshot Monitoring Daemon for Servers
========================================

This script runs as a daemon service taking continuous screenshots at defined intervals.
Includes monitoring, cleanup, and health checks.

Requirements:
- pyautogui
- Pillow
- xvfb (for headless operation)

Usage:
    python3 screenshot_cron.py start          # Start daemon
    python3 screenshot_cron.py stop           # Stop daemon
    python3 screenshot_cron.py status         # Check status
    python3 screenshot_cron.py monitor        # Monitor mode
    python3 screenshot_cron.py single         # Single screenshot

Systemd service example:
    sudo systemctl start screenshot-daemon
"""

import os
import sys
import logging
import time
import signal
import threading
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path

try:
    import pyautogui
    from PIL import Image
    import requests
except ImportError as e:
    print(f"Error: Required library not installed: {e}")
    print("Install with: pip3 install pyautogui Pillow requests")
    sys.exit(1)

# Configuration
CONFIG = {
    "output_dir": "/Users/primetech/Documents/ss/screenshots",
    "regions": {
        "full_screen": None,  # None means full screen
        "top_left": (0, 0, 960, 540),  # Top-left quarter
        "top_right": (960, 0, 960, 540),  # Top-right quarter
        "bottom_left": (0, 540, 960, 540),  # Bottom-left quarter
        "bottom_right": (960, 540, 960, 540),  # Bottom-right quarter
        "center": (480, 270, 960, 540),  # Center region
        "taskbar": (0, 1040, 1920, 40),  # Windows taskbar area
        "header": (0, 0, 1920, 100),  # Top header area
        "custom": (100, 100, 800, 600)  # Custom region
    },
    "active_regions": ["full_screen"],  # Which regions to capture
    "interval": 60,  # seconds between screenshots
    "keep_days": 7,
    "max_files": 1000,
    "log_level": "INFO",
    "health_check_interval": 300,  # 5 minutes
    "enable_cleanup": True,
    "cleanup_interval": 3600,  # 1 hour
    "telegram": {
        "enabled": True,
        "bot_token": "7316358170:AAHKY7d37TclDcZg8b-d4CgfUjJ5HeI-QhQ",  # Replace with your bot token
        "region_chats": {
            "full_screen": "-1002745524480",  # Main group
            "top_left": "-1002745524480",    # Top left group
            "top_right": "-1002745524480",   # Top right group
            "bottom_left": "-1001234567893", # Bottom left group
            "bottom_right": "-1002745524480", # Bottom right group
            "center": "-1002745524480",      # Center group
            "taskbar": "-1002745524480",     # Taskbar group
            "header": "-1002745524480",      # Header group
            "custom": "-1002745524480"       # Custom group
        },
        "send_immediately": True,  # Send immediately after screenshot
        "delete_after_send": True,  # Delete screenshot after successful Telegram send
        "message_template": "🖥️ Screenshot: {region_name}\n📅 Time: {timestamp}\n📏 Size: {file_size} bytes",
        "retry_attempts": 3,
        "retry_delay": 5  # seconds
    }
}

# PID file for daemon management
PID_FILE = "/Users/primetech/Documents/ss/screenshot-daemon.pid"

# Disable pyautogui fail-safe (important for headless operation)
pyautogui.FAILSAFE = False

class TelegramBot:
    def __init__(self, bot_token, region_chats, message_template, retry_attempts=3, retry_delay=5):
        self.bot_token = bot_token
        self.region_chats = region_chats
        self.message_template = message_template
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
    
    def send_photo(self, region_name, file_path, timestamp, file_size):
        """Send screenshot to specific Telegram group based on region"""
        if region_name not in self.region_chats:
            self.logger.warning(f"No Telegram chat configured for region: {region_name}")
            return False
        
        chat_id = self.region_chats[region_name]
        
        # Format message
        message = self.message_template.format(
            region_name=region_name,
            timestamp=timestamp,
            file_size=file_size
        )
        
        # Send with retry logic
        for attempt in range(self.retry_attempts):
            try:
                with open(file_path, 'rb') as photo:
                    url = f"{self.base_url}/sendPhoto"
                    data = {
                        'chat_id': chat_id,
                        'caption': message,
                        'parse_mode': 'HTML'
                    }
                    files = {'photo': photo}
                    
                    response = requests.post(url, data=data, files=files, timeout=30)
                    
                    if response.status_code == 200:
                        self.logger.info(f"✅ Screenshot sent to Telegram group for region '{region_name}'")
                        return True
                    else:
                        error_msg = f"❌ Telegram API error: {response.status_code} - {response.text}"
                        self.logger.error(error_msg)
                        
            except Exception as e:
                error_msg = f"❌ Failed to send screenshot to Telegram (attempt {attempt + 1}/{self.retry_attempts}): {e}"
                self.logger.error(error_msg)
                
                if attempt < self.retry_attempts - 1:
                    self.logger.info(f"⏳ Retrying in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
        
        return False
    
    def send_text_message(self, chat_id, message):
        """Send text message to specific chat"""
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                self.logger.info(f"✅ Text message sent to chat {chat_id}")
                return True
            else:
                self.logger.error(f"❌ Failed to send text message: {response.status_code} - {response.text}")
                
        except Exception as e:
            self.logger.error(f"❌ Failed to send text message: {e}")
        
        return False
    
    def test_connection(self):
        """Test bot connection and get bot info"""
        try:
            url = f"{self.base_url}/getMe"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                bot_info = response.json()
                if bot_info['ok']:
                    bot_data = bot_info['result']
                    self.logger.info(f"✅ Bot connected: @{bot_data['username']} ({bot_data['first_name']})")
                    return True
                    
        except Exception as e:
            self.logger.error(f"❌ Bot connection test failed: {e}")
        
        return False
    
    def send_startup_message(self):
        """Send startup message to all configured groups"""
        message = "🚀 Screenshot Daemon Started!\n📊 Monitoring active regions..."
        
        for region_name, chat_id in self.region_chats.items():
            self.send_text_message(chat_id, f"{message}\n🎯 Region: {region_name}")
    
    def send_shutdown_message(self):
        """Send shutdown message to all configured groups"""
        message = "🛑 Screenshot Daemon Stopped"
        
        for region_name, chat_id in self.region_chats.items():
            self.send_text_message(chat_id, f"{message}\n🎯 Region: {region_name}")

class ScreenshotDaemon:
    def __init__(self, config):
        self.config = config
        self.output_dir = Path(config["output_dir"])
        self.regions = config["regions"]
        self.active_regions = config["active_regions"]
        self.interval = config["interval"]
        self.running = False
        self.thread = None
        self.stats = {
            "total_screenshots": 0,
            "failed_screenshots": 0,
            "telegram_sent": 0,
            "telegram_failed": 0,
            "start_time": None,
            "last_screenshot": None,
            "last_cleanup": None
        }
        
        # Initialize Telegram bot if enabled
        self.telegram_bot = None
        if config["telegram"]["enabled"]:
            self.telegram_bot = TelegramBot(
                bot_token=config["telegram"]["bot_token"],
                region_chats=config["telegram"]["region_chats"],
                message_template=config["telegram"]["message_template"],
                retry_attempts=config["telegram"]["retry_attempts"],
                retry_delay=config["telegram"]["retry_delay"]
            )
        
        self.setup_logging()
        self.ensure_output_directory()
        self.setup_signal_handlers()
        
        # Create PID file
        self.create_pid_file()
        
        # Test Telegram connection if enabled
        if self.telegram_bot and not self.telegram_bot.test_connection():
            self.logger.warning("⚠️ Telegram bot connection test failed - screenshots will be saved locally only")
    
    def create_pid_file(self):
        """Create PID file for daemon management"""
        try:
            with open(PID_FILE, 'w') as f:
                f.write(str(os.getpid()))
        except Exception as e:
            self.logger.warning(f"Could not create PID file: {e}")
    
    def remove_pid_file(self):
        """Remove PID file"""
        try:
            if os.path.exists(PID_FILE):
                os.unlink(PID_FILE)
        except Exception as e:
            self.logger.warning(f"Could not remove PID file: {e}")
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)
    
    def setup_logging(self):
        """Setup logging configuration"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = self.output_dir / "screenshot_daemon.log"
        
        logging.basicConfig(
            level=getattr(logging, self.config["log_level"]),
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def ensure_output_directory(self):
        """Ensure the output directory exists"""
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Output directory ready: {self.output_dir}")
        except Exception as e:
            self.logger.error(f"Failed to create output directory {self.output_dir}: {e}")
            sys.exit(1)
    
    def generate_filename(self, region_name="screenshot"):
        """Generate timestamped filename with region name"""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{region_name}_{timestamp}.png"
        return self.output_dir / filename
    
    def take_screenshot(self):
        """Take screenshots of all active regions"""
        screenshots_taken = 0
        
        for region_name in self.active_regions:
            if region_name not in self.regions:
                self.logger.warning(f"Unknown region: {region_name}")
                continue
                
            try:
                region = self.regions[region_name]
                self.logger.debug(f"Taking screenshot of region '{region_name}': {region}")
                
                # Take screenshot of the specified region
                if region is None:
                    # Full screen
                    screenshot = pyautogui.screenshot()
                else:
                    # Specific region
                    screenshot = pyautogui.screenshot(region=region)
                
                # Generate filename and save
                filepath = self.generate_filename(region_name)
                screenshot.save(filepath)
                
                # Log success
                file_size = filepath.stat().st_size
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                self.logger.info(f"Screenshot saved: {filepath.name} ({file_size} bytes)")
                
                # Send to Telegram if enabled
                if self.telegram_bot and self.config["telegram"]["send_immediately"]:
                    telegram_sent = self.telegram_bot.send_photo(region_name, filepath, timestamp, file_size)
                    if telegram_sent:
                        self.stats["telegram_sent"] += 1
                        
                        # Delete file after successful send if configured
                        if self.config["telegram"]["delete_after_send"]:
                            try:
                                filepath.unlink()
                                self.logger.info(f"🗑️ Screenshot deleted after Telegram send: {filepath.name}")
                            except Exception as e:
                                self.logger.warning(f"Failed to delete screenshot after Telegram send: {e}")
                    else:
                        self.stats["telegram_failed"] += 1
                
                screenshots_taken += 1
                
            except Exception as e:
                self.stats["failed_screenshots"] += 1
                self.logger.error(f"Screenshot failed for region '{region_name}': {str(e)}")
        
        # Update stats
        self.stats["total_screenshots"] += screenshots_taken
        self.stats["last_screenshot"] = datetime.now()
        
        return screenshots_taken > 0
    
    def cleanup_old_screenshots(self):
        """Clean up old screenshots based on age and count"""
        try:
            current_time = time.time()
            cutoff_time = current_time - (self.config["keep_days"] * 24 * 60 * 60)
            
            deleted_count = 0
            # Include all region patterns
            patterns = [f"{region_name}_*.png" for region_name in self.regions.keys()]
            patterns.append("screenshot_*.png")  # Legacy pattern
            
            files = []
            for pattern in patterns:
                files.extend(self.output_dir.glob(pattern))
            
            # Sort by creation time
            files.sort(key=lambda x: x.stat().st_mtime)
            
            # Remove files older than keep_days
            for file_path in files:
                if file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    deleted_count += 1
            
            # Keep only max_files newest files
            remaining_files = [f for f in files if f.exists()]
            if len(remaining_files) > self.config["max_files"]:
                files_to_remove = remaining_files[:len(remaining_files) - self.config["max_files"]]
                for file_path in files_to_remove:
                    file_path.unlink()
                    deleted_count += 1
            
            if deleted_count > 0:
                self.logger.info(f"Cleaned up {deleted_count} old screenshots")
            
            self.stats["last_cleanup"] = datetime.now()
                
        except Exception as e:
            self.logger.warning(f"Failed to cleanup old screenshots: {e}")
    
    def health_check(self):
        """Perform health checks"""
        try:
            # Check disk space
            disk_usage = os.statvfs(self.output_dir)
            free_space = disk_usage.f_frsize * disk_usage.f_bavail
            free_space_mb = free_space / (1024 * 1024)
            
            if free_space_mb < 100:  # Less than 100MB
                self.logger.warning(f"Low disk space: {free_space_mb:.1f} MB free")
            
            # Check if we can write files
            test_file = self.output_dir / "health_check.tmp"
            test_file.write_text("health check")
            test_file.unlink()
            
            self.logger.debug("Health check passed")
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
    
    def screenshot_loop(self):
        """Main screenshot loop"""
        self.logger.info("Screenshot daemon started")
        self.stats["start_time"] = datetime.now()
        
        last_cleanup = 0
        last_health_check = 0
        
        while self.running:
            try:
                current_time = time.time()
                
                # Take screenshot
                self.take_screenshot()
                
                # Periodic cleanup
                if (self.config["enable_cleanup"] and 
                    current_time - last_cleanup > self.config["cleanup_interval"]):
                    self.cleanup_old_screenshots()
                    last_cleanup = current_time
                
                # Health check
                if current_time - last_health_check > self.config["health_check_interval"]:
                    self.health_check()
                    last_health_check = current_time
                
                # Wait for next interval
                time.sleep(self.interval)
                
            except Exception as e:
                self.logger.error(f"Error in screenshot loop: {e}")
                time.sleep(10)  # Wait before retry
        
        self.logger.info("Screenshot daemon stopped")
    
    def start(self):
        """Start the daemon"""
        if self.running:
            self.logger.warning("Daemon is already running")
            return
        
        # Check if running in headless environment
        if not os.environ.get('DISPLAY'):
            self.logger.warning("No DISPLAY environment variable found. Make sure to run with xvfb-run.")
        
        self.running = True
        self.thread = threading.Thread(target=self.screenshot_loop)
        self.thread.daemon = True
        self.thread.start()
        
        # Send startup message to Telegram
        if self.telegram_bot:
            self.telegram_bot.send_startup_message()
        
        try:
            # Keep main thread alive
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        """Stop the daemon"""
        if not self.running:
            return
        
        # Send shutdown message to Telegram
        if self.telegram_bot:
            self.telegram_bot.send_shutdown_message()
        
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        
        self.remove_pid_file()
        self.logger.info("Screenshot daemon stopped")
    
    def get_status(self):
        """Get daemon status"""
        uptime = None
        if self.stats["start_time"]:
            uptime = str(datetime.now() - self.stats["start_time"])
        
        return {
            "running": self.running,
            "output_dir": str(self.output_dir),
            "interval": self.interval,
            "regions": self.regions,
            "active_regions": self.active_regions,
            "uptime": uptime,
            "stats": self.stats,
            "config": self.config
        }
    
    def monitor_mode(self):
        """Interactive monitoring mode"""
        print("Screenshot Daemon Monitor")
        print("=" * 30)
        print("Press Ctrl+C to exit")
        
        try:
            while True:
                os.system('clear' if os.name == 'posix' else 'cls')
                
                status = self.get_status()
                print(f"Status: {'🟢 Running' if status['running'] else '🔴 Stopped'}")
                print(f"Output Directory: {status['output_dir']}")
                print(f"Screenshot Interval: {status['interval']} seconds")
                print(f"Active Regions: {', '.join(status['active_regions'])}")
                
                if status['uptime']:
                    print(f"Uptime: {status['uptime']}")
                
                print(f"\nRegions Configuration:")
                for region_name, region_coords in status['regions'].items():
                    active = "✅" if region_name in status['active_regions'] else "⭕"
                    print(f"  {active} {region_name}: {region_coords}")
                
                print(f"\nStatistics:")
                print(f"  Total Screenshots: {status['stats']['total_screenshots']}")
                print(f"  Failed Screenshots: {status['stats']['failed_screenshots']}")
                print(f"  Telegram Sent: {status['stats']['telegram_sent']}")
                print(f"  Telegram Failed: {status['stats']['telegram_failed']}")
                
                if status['stats']['last_screenshot']:
                    print(f"  Last Screenshot: {status['stats']['last_screenshot']}")
                
                if status['stats']['last_cleanup']:
                    print(f"  Last Cleanup: {status['stats']['last_cleanup']}")
                
                # Show Telegram status
                if self.telegram_bot:
                    print(f"\n📱 Telegram Status:")
                    print(f"  Bot Token: {'✅ Configured' if self.config['telegram']['bot_token'] != 'YOUR_BOT_TOKEN' else '❌ Not configured'}")
                    print(f"  Auto Send: {'✅ Enabled' if self.config['telegram']['send_immediately'] else '❌ Disabled'}")
                    print(f"  Delete After Send: {'✅ Enabled' if self.config['telegram']['delete_after_send'] else '❌ Disabled'}")
                    print(f"  Configured Chats: {len(self.config['telegram']['region_chats'])}")
                
                # Show recent files
                patterns = [f"{region_name}_*.png" for region_name in status['regions'].keys()]
                patterns.append("screenshot_*.png")
                
                recent_files = []
                for pattern in patterns:
                    recent_files.extend(self.output_dir.glob(pattern))
                
                recent_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                
                print(f"\nRecent Files ({len(recent_files)} total):")
                for i, file in enumerate(recent_files[:10]):  # Show more files
                    mtime = datetime.fromtimestamp(file.stat().st_mtime)
                    size = file.stat().st_size
                    print(f"  {i+1}. {file.name} ({size} bytes) - {mtime}")
                
                time.sleep(5)
                
        except KeyboardInterrupt:
            print("\nMonitoring stopped")

# Keep the original ScreenshotManager for backward compatibility
class ScreenshotManager:
    def __init__(self, output_dir, regions=None, active_regions=None):
        self.output_dir = Path(output_dir)
        self.regions = regions or {"screenshot": (100, 100, 800, 600)}
        self.active_regions = active_regions or ["screenshot"]
        self.setup_logging()
        self.ensure_output_directory()
    
    def setup_logging(self):
        """Setup logging configuration"""
        # Ensure output directory exists for log file
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = self.output_dir / "screenshot.log"
        
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, CONFIG["log_level"]),
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def ensure_output_directory(self):
        """Ensure the output directory exists"""
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Output directory ready: {self.output_dir}")
        except Exception as e:
            self.logger.error(f"Failed to create output directory {self.output_dir}: {e}")
            sys.exit(1)
    
    def generate_filename(self, region_name="screenshot"):
        """Generate timestamped filename"""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{region_name}_{timestamp}.png"
        return self.output_dir / filename
    
    def take_screenshot(self):
        """Take screenshots of all active regions"""
        screenshots_taken = 0
        
        for region_name in self.active_regions:
            if region_name not in self.regions:
                self.logger.warning(f"Unknown region: {region_name}")
                continue
                
            try:
                region = self.regions[region_name]
                self.logger.info(f"Taking screenshot of region '{region_name}': {region}")
                
                # Take screenshot of the specified region
                if region is None:
                    # Full screen
                    screenshot = pyautogui.screenshot()
                else:
                    # Specific region
                    screenshot = pyautogui.screenshot(region=region)
                
                # Generate filename and save
                filepath = self.generate_filename(region_name)
                screenshot.save(filepath)
                
                # Log success
                success_msg = f"Screenshot saved successfully: {filepath}"
                print(success_msg)
                self.logger.info(success_msg)
                
                # Log file size for monitoring
                file_size = filepath.stat().st_size
                self.logger.info(f"File size: {file_size} bytes")
                
                screenshots_taken += 1
                
            except Exception as e:
                error_msg = f"Screenshot failed for region '{region_name}': {str(e)}"
                print(error_msg, file=sys.stderr)
                self.logger.error(error_msg)
        
        if screenshots_taken == 0:
            sys.exit(1)
        
        return screenshots_taken
    
    def cleanup_old_screenshots(self, keep_days=7):
        """Optional: Clean up old screenshots (keep last N days)"""
        try:
            import time
            current_time = time.time()
            cutoff_time = current_time - (keep_days * 24 * 60 * 60)
            
            deleted_count = 0
            # Include all region patterns
            patterns = [f"{region_name}_*.png" for region_name in self.regions.keys()]
            patterns.append("screenshot_*.png")  # Legacy pattern
            
            files = []
            for pattern in patterns:
                files.extend(self.output_dir.glob(pattern))
            
            for file_path in files:
                if file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
                    deleted_count += 1
            
            if deleted_count > 0:
                self.logger.info(f"Cleaned up {deleted_count} old screenshots")
                
        except Exception as e:
            self.logger.warning(f"Failed to cleanup old screenshots: {e}")

def main():
    """Main function with command line arguments"""
    parser = argparse.ArgumentParser(description='Screenshot Monitoring Daemon')
    parser.add_argument('command', choices=['start', 'stop', 'status', 'monitor', 'single', 'config', 'regions', 'telegram'],
                       help='Command to execute')
    parser.add_argument('--config', '-c', help='Configuration file path')
    parser.add_argument('--interval', '-i', type=int, help='Screenshot interval in seconds')
    parser.add_argument('--regions', '-r', help='Active regions (comma-separated)')
    parser.add_argument('--output', '-o', help='Output directory')
    parser.add_argument('--add-region', help='Add custom region as "name:x,y,width,height"')
    parser.add_argument('--bot-token', help='Telegram bot token')
    parser.add_argument('--test-telegram', action='store_true', help='Test Telegram bot connection')
    parser.add_argument('--delete-after-send', action='store_true', help='Delete screenshots after successful Telegram send')
    parser.add_argument('--keep-after-send', action='store_true', help='Keep screenshots after Telegram send')
    
    args = parser.parse_args()
    
    # Override config with command line arguments
    config = CONFIG.copy()
    if args.interval:
        config["interval"] = args.interval
    if args.regions:
        config["active_regions"] = [r.strip() for r in args.regions.split(',')]
    if args.output:
        config["output_dir"] = args.output
    if args.add_region:
        try:
            name, coords = args.add_region.split(':')
            x, y, w, h = map(int, coords.split(','))
            config["regions"][name] = (x, y, w, h)
            if name not in config["active_regions"]:
                config["active_regions"].append(name)
        except ValueError:
            print("Error: Invalid region format. Use 'name:x,y,width,height'")
            sys.exit(1)
    if args.bot_token:
        config["telegram"]["bot_token"] = args.bot_token
        config["telegram"]["enabled"] = True
    if args.delete_after_send:
        config["telegram"]["delete_after_send"] = True
    if args.keep_after_send:
        config["telegram"]["delete_after_send"] = False
    
    # Commands
    if args.command == 'start':
        daemon = ScreenshotDaemon(config)
        daemon.start()
    
    elif args.command == 'stop':
        if os.path.exists(PID_FILE):
            with open(PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            try:
                os.kill(pid, signal.SIGTERM)
                print(f"Stopped daemon with PID {pid}")
            except ProcessLookupError:
                print("Daemon is not running")
                os.unlink(PID_FILE)
        else:
            print("Daemon is not running (no PID file)")
    
    elif args.command == 'status':
        if os.path.exists(PID_FILE):
            with open(PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            try:
                os.kill(pid, 0)  # Test if process exists
                print(f"✅ Daemon is running (PID: {pid})")
                
                # Show recent files
                output_dir = Path(config["output_dir"])
                if output_dir.exists():
                    patterns = [f"{region_name}_*.png" for region_name in config["regions"].keys()]
                    patterns.append("screenshot_*.png")
                    
                    recent_files = []
                    for pattern in patterns:
                        recent_files.extend(output_dir.glob(pattern))
                    
                    recent_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                    
                    print(f"📁 Output directory: {output_dir}")
                    print(f"🎯 Active regions: {', '.join(config['active_regions'])}")
                    print(f"📸 Total screenshots: {len(recent_files)}")
                    
                    if recent_files:
                        latest = recent_files[0]
                        mtime = datetime.fromtimestamp(latest.stat().st_mtime)
                        print(f"🕐 Last screenshot: {mtime} ({latest.name})")
                
            except ProcessLookupError:
                print("❌ Daemon is not running (stale PID file)")
                os.unlink(PID_FILE)
        else:
            print("❌ Daemon is not running")
    
    elif args.command == 'monitor':
        daemon = ScreenshotDaemon(config)
        daemon.monitor_mode()
    
    elif args.command == 'single':
        # Single screenshot (backward compatibility)
        if not os.environ.get('DISPLAY'):
            print("Warning: No DISPLAY environment variable found. Make sure to run with xvfb-run.")
        
        screenshot_manager = ScreenshotManager(
            config["output_dir"], 
            config["regions"], 
            config["active_regions"]
        )
        screenshot_manager.take_screenshot()
        screenshot_manager.cleanup_old_screenshots(keep_days=7)
    
    elif args.command == 'config':
        print(json.dumps(config, indent=2))
    
    elif args.command == 'regions':
        print("📍 Available Regions:")
        print("=" * 50)
        for region_name, coords in config["regions"].items():
            active = "✅ ACTIVE" if region_name in config["active_regions"] else "⭕ INACTIVE"
            print(f"{active} - {region_name}: {coords}")
        print()
        print("💡 Usage examples:")
        print(f"  Activate regions: python3 {sys.argv[0]} start --regions 'top_left,center'")
        print(f"  Add custom region: python3 {sys.argv[0]} start --add-region 'my_region:0,0,500,300'")
        print(f"  Single screenshot: python3 {sys.argv[0]} single --regions 'full_screen'")
    
    elif args.command == 'telegram':
        print("📱 Telegram Configuration:")
        print("=" * 50)
        
        telegram_config = config["telegram"]
        
        print(f"Enabled: {'✅ Yes' if telegram_config['enabled'] else '❌ No'}")
        print(f"Bot Token: {'✅ Configured' if telegram_config['bot_token'] != 'YOUR_BOT_TOKEN' else '❌ Not configured'}")
        print(f"Send Immediately: {'✅ Yes' if telegram_config['send_immediately'] else '❌ No'}")
        print(f"Delete After Send: {'✅ Yes' if telegram_config['delete_after_send'] else '❌ No'}")
        print(f"Retry Attempts: {telegram_config['retry_attempts']}")
        print(f"Retry Delay: {telegram_config['retry_delay']} seconds")
        
        print(f"\n📍 Region Chat Mapping:")
        for region_name, chat_id in telegram_config["region_chats"].items():
            active = "✅" if region_name in config["active_regions"] else "⭕"
            print(f"  {active} {region_name} → {chat_id}")
        
        print(f"\n📝 Message Template:")
        print(f"  {telegram_config['message_template']}")
        
        # Test connection if requested
        if args.test_telegram and telegram_config["bot_token"] != "YOUR_BOT_TOKEN":
            print(f"\n🔍 Testing Telegram connection...")
            bot = TelegramBot(
                telegram_config["bot_token"],
                telegram_config["region_chats"],
                telegram_config["message_template"]
            )
            if bot.test_connection():
                print("✅ Telegram bot connection successful!")
            else:
                print("❌ Telegram bot connection failed!")
        
        print(f"\n💡 Setup Instructions:")
        print("1. Create a Telegram bot: https://t.me/BotFather")
        print("2. Get your bot token")
        print("3. Add bot to your groups")
        print("4. Get group chat IDs (use @userinfobot)")
        print("5. Update the configuration:")
        print(f"   python3 {sys.argv[0]} start --bot-token YOUR_BOT_TOKEN")
        print(f"6. Test connection:")
        print(f"   python3 {sys.argv[0]} telegram --test-telegram")

if __name__ == "__main__":
    main()
