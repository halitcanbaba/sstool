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
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.firefox.service import Service as FirefoxService
    
    # Set DISPLAY environment variable for headless operation if not set
    if not os.environ.get('DISPLAY'):
        os.environ['DISPLAY'] = ':99'
        print("Warning: DISPLAY environment variable not set, using :99")
        
except ImportError as e:
    print(f"Error: Required library not installed: {e}")
    print("Install with: pip3 install pyautogui Pillow requests selenium webdriver-manager")
    sys.exit(1)

# Configuration
CONFIG = {
    "output_dir": "/var/screenshots",
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
    "web_screenshots": {
        "enabled": True,
        "browser": "chrome",  # 'firefox' or 'chrome'
        "headless": True,
        "window_size": (1920, 1080),
        "urls": {
            "google": {
                "url": "https://www.google.com",
                "wait_time": 3,
                "element_selector": None,  # Wait for specific element
                "telegram_chat_id": "-1002745524480"
            },
            "github": {
                "url": "https://github.com",
                "wait_time": 5,
                "element_selector": ".Header",
                "telegram_chat_id": "-1002745524480"
            },
            "stackoverflow": {
                "url": "https://stackoverflow.com",
                "wait_time": 3,
                "element_selector": None,
                "telegram_chat_id": "-1002745524480"
            }
        },
        "active_urls": ["google"],  # Which URLs to capture
        "interval": 300,  # 5 minutes between web screenshots
        "delete_after_send": True,
        "scheduled_regions": {
            "enabled": True,
            "schedule": {
                "09:00": {
                    "url": "https://www.google.com",
                    "region": "viewport",  # or "full_page", "element", "coordinates"
                    "region_config": None,  # For element: CSS selector, for coordinates: [x,y,w,h]
                    "telegram_chat_id": "-1002745524480",
                    "description": "Google Ana Sayfa - Sabah Kontrolü"
                },
                "12:00": {
                    "url": "https://github.com",
                    "region": "element",
                    "region_config": ".Header",
                    "telegram_chat_id": "-1002745524480",
                    "description": "GitHub Header - Öğle Kontrolü"
                },
                "15:00": {
                    "url": "https://stackoverflow.com",
                    "region": "coordinates",
                    "region_config": [0, 0, 1200, 800],
                    "telegram_chat_id": "-1002745524480",
                    "description": "StackOverflow Üst Kısım - Öğleden Sonra"
                },
                "18:00": {
                    "url": "https://www.google.com",
                    "region": "viewport",
                    "region_config": None,
                    "telegram_chat_id": "-1002745524480",
                    "description": "Google Ana Sayfa - Akşam Kontrolü"
                },
                "21:00": {
                    "url": "https://github.com",
                    "region": "viewport",
                    "region_config": None,
                    "telegram_chat_id": "-1002745524480",
                    "description": "GitHub Ana Sayfa - Gece Kontrolü"
                }
            }
        }
    },
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
PID_FILE = "/var/run/screenshot-daemon.pid"

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
        
        # Try to create a test file to check permissions
        try:
            test_file = self.output_dir / "test_permissions.tmp"
            test_file.write_text("permission test")
            test_file.unlink()
        except Exception as e:
            print(f"Warning: Cannot write to {self.output_dir}: {e}")
            # Fall back to /tmp for logging
            log_file = Path("/tmp/screenshot_daemon.log")
            print(f"Using fallback log file: {log_file}")
        
        # Configure logging handlers
        handlers = [logging.StreamHandler(sys.stdout)]
        
        # Add file handler only if we can write to the log file
        try:
            handlers.append(logging.FileHandler(log_file))
        except Exception as e:
            print(f"Warning: Cannot create log file {log_file}: {e}")
            print("Logging will only go to stdout")
        
        logging.basicConfig(
            level=getattr(logging, self.config["log_level"]),
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=handlers
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
    
    def take_web_screenshots(self):
        """Take screenshots of configured web pages"""
        if not self.config["web_screenshots"]["enabled"]:
            return
        
        web_config = self.config["web_screenshots"]
        active_urls = web_config.get("active_urls", [])
        
        if not active_urls:
            return
        
        # Initialize web screenshot handler
        web_handler = WebScreenshot(
            browser=web_config["browser"],
            headless=web_config["headless"],
            window_size=web_config["window_size"]
        )
        
        if not web_handler.start_driver():
            self.logger.error("Failed to start web driver")
            return
        
        try:
            for url_name in active_urls:
                if url_name not in web_config["urls"]:
                    self.logger.warning(f"Unknown URL config: {url_name}")
                    continue
                
                url_config = web_config["urls"][url_name]
                
                try:
                    # Generate filename for web screenshot
                    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    filename = f"web_{url_name}_{timestamp}.png"
                    filepath = self.output_dir / filename
                    
                    # Take screenshot
                    success = web_handler.take_screenshot(
                        url=url_config["url"],
                        output_path=str(filepath),
                        wait_time=url_config["wait_time"],
                        element_selector=url_config.get("element_selector")
                    )
                    
                    if success:
                        file_size = filepath.stat().st_size
                        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        self.logger.info(f"Web screenshot saved: {filename} ({file_size} bytes)")
                        
                        # Send to Telegram if enabled
                        if self.telegram_bot and url_config.get("telegram_chat_id"):
                            message = f"🌐 Web Screenshot: {url_name}\n📅 Time: {timestamp_str}\n🔗 URL: {url_config['url']}\n📏 Size: {file_size} bytes"
                            
                            try:
                                # Send to specific chat
                                url = f"https://api.telegram.org/bot{self.telegram_bot.bot_token}/sendPhoto"
                                with open(filepath, 'rb') as photo:
                                    data = {
                                        'chat_id': url_config["telegram_chat_id"],
                                        'caption': message,
                                        'parse_mode': 'HTML'
                                    }
                                    files = {'photo': photo}
                                    
                                    response = requests.post(url, data=data, files=files, timeout=30)
                                    
                                    if response.status_code == 200:
                                        self.logger.info(f"✅ Web screenshot sent to Telegram: {url_name}")
                                        self.stats["telegram_sent"] += 1
                                        
                                        # Delete file after successful send if configured
                                        if web_config["delete_after_send"]:
                                            try:
                                                filepath.unlink()
                                                self.logger.info(f"🗑️ Web screenshot deleted after Telegram send: {filename}")
                                            except Exception as e:
                                                self.logger.warning(f"Failed to delete web screenshot: {e}")
                                    else:
                                        self.logger.error(f"❌ Failed to send web screenshot to Telegram: {response.status_code}")
                                        self.stats["telegram_failed"] += 1
                                        
                            except Exception as e:
                                self.logger.error(f"❌ Error sending web screenshot to Telegram: {e}")
                                self.stats["telegram_failed"] += 1
                        
                        self.stats["total_screenshots"] += 1
                        
                    else:
                        self.logger.error(f"Failed to take web screenshot: {url_name}")
                        self.stats["failed_screenshots"] += 1
                        
                except Exception as e:
                    self.logger.error(f"Error taking web screenshot for {url_name}: {e}")
                    self.stats["failed_screenshots"] += 1
        
        finally:
            web_handler.stop_driver()

    def check_scheduled_web_screenshots(self):
        """Check and execute scheduled web screenshots"""
        try:
            web_config = self.config["web_screenshots"]
            if not web_config["enabled"] or not web_config["scheduled_regions"]["enabled"]:
                return
            
            current_time = datetime.now()
            current_time_str = current_time.strftime("%H:%M")
            
            schedule = web_config["scheduled_regions"]["schedule"]
            
            # Check if current time matches any scheduled time
            if current_time_str in schedule:
                scheduled_config = schedule[current_time_str]
                
                # Check if we already took screenshot for this hour
                last_run_key = f"last_scheduled_{current_time_str.replace(':', '_')}"
                last_run = getattr(self, last_run_key, None)
                
                if last_run and last_run.date() == current_time.date() and last_run.hour == current_time.hour:
                    # Already took screenshot this hour
                    return
                
                self.logger.info(f"🕐 Executing scheduled web screenshot for {current_time_str}")
                
                # Take scheduled screenshot
                success = self.take_scheduled_web_screenshot(scheduled_config, current_time_str)
                
                if success:
                    # Mark as completed for this hour
                    setattr(self, last_run_key, current_time)
                    self.logger.info(f"✅ Scheduled web screenshot completed for {current_time_str}")
                else:
                    self.logger.error(f"❌ Scheduled web screenshot failed for {current_time_str}")
                    
        except Exception as e:
            self.logger.error(f"Error checking scheduled web screenshots: {e}")

    def take_scheduled_web_screenshot(self, schedule_config, schedule_time):
        """Take a scheduled web screenshot"""
        try:
            url = schedule_config["url"]
            region_type = schedule_config["region"]
            region_config = schedule_config["region_config"]
            chat_id = schedule_config["telegram_chat_id"]
            description = schedule_config["description"]
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"scheduled_{schedule_time.replace(':', '-')}_{timestamp}.png"
            filepath = self.output_dir / filename
            
            # Initialize web screenshot handler
            web_handler = WebScreenshot(
                browser=self.config["web_screenshots"]["browser"],
                headless=self.config["web_screenshots"]["headless"],
                window_size=self.config["web_screenshots"]["window_size"]
            )
            
            if not web_handler.start_driver():
                self.logger.error("Failed to start WebDriver for scheduled screenshot")
                return False
            
            try:
                # Take screenshot based on region type
                success = web_handler.take_region_screenshot(
                    url=url,
                    output_path=str(filepath),
                    region_type=region_type,
                    region_config=region_config,
                    wait_time=3
                )
                
                if success:
                    self.logger.info(f"📸 Scheduled web screenshot saved: {filepath}")
                    
                    # Send to Telegram if enabled
                    if self.telegram_bot and chat_id:
                        try:
                            file_size = filepath.stat().st_size
                            timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            
                            # Custom message for scheduled screenshots
                            message = f"🕐 Scheduled Web Screenshot\n📋 {description}\n🌐 URL: {url}\n🎯 Region: {region_type}\n📅 Time: {timestamp_str}\n📏 Size: {file_size} bytes"
                            
                            # Send photo directly to specific chat
                            with open(filepath, 'rb') as photo:
                                url_send = f"https://api.telegram.org/bot{self.telegram_bot.bot_token}/sendPhoto"
                                data = {
                                    'chat_id': chat_id,
                                    'caption': message,
                                    'parse_mode': 'HTML'
                                }
                                files = {'photo': photo}
                                
                                response = requests.post(url_send, data=data, files=files, timeout=30)
                                
                                if response.status_code == 200:
                                    self.logger.info(f"✅ Scheduled web screenshot sent to Telegram: {description}")
                                    self.stats["telegram_sent"] += 1
                                    
                                    # Delete file after successful send if configured
                                    if self.config["web_screenshots"]["delete_after_send"]:
                                        try:
                                            filepath.unlink()
                                            self.logger.info(f"🗑️ Scheduled screenshot deleted after Telegram send: {filename}")
                                        except Exception as e:
                                            self.logger.warning(f"Failed to delete scheduled screenshot: {e}")
                                else:
                                    self.logger.error(f"❌ Failed to send scheduled screenshot to Telegram: {response.status_code}")
                                    self.stats["telegram_failed"] += 1
                                    
                        except Exception as e:
                            self.logger.error(f"❌ Error sending scheduled screenshot to Telegram: {e}")
                            self.stats["telegram_failed"] += 1
                    
                    self.stats["total_screenshots"] += 1
                    return True
                else:
                    self.logger.error(f"Failed to take scheduled web screenshot: {url}")
                    self.stats["failed_screenshots"] += 1
                    return False
                    
            finally:
                web_handler.stop_driver()
                
        except Exception as e:
            self.logger.error(f"Error taking scheduled web screenshot: {e}")
            self.stats["failed_screenshots"] += 1
            return False

    def start(self):
        """Start the screenshot daemon"""
        if self.running:
            self.logger.warning("Daemon is already running")
            return
        
        self.running = True
        self.stats["start_time"] = datetime.now()
        
        # Send startup message to Telegram
        if self.telegram_bot:
            self.telegram_bot.send_startup_message()
        
        self.logger.info("🚀 Screenshot daemon started")
        self.logger.info(f"📁 Output directory: {self.output_dir}")
        self.logger.info(f"📸 Active regions: {', '.join(self.active_regions)}")
        self.logger.info(f"⏱️ Screenshot interval: {self.interval} seconds")
        
        # Start background threads
        self.thread = threading.Thread(target=self._daemon_loop)
        self.thread.daemon = True
        self.thread.start()
        
        # Keep main thread alive
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        finally:
            self.stop()

    def stop(self):
        """Stop the screenshot daemon"""
        if not self.running:
            return
        
        self.logger.info("🛑 Stopping screenshot daemon...")
        self.running = False
        
        # Send shutdown message to Telegram
        if self.telegram_bot:
            self.telegram_bot.send_shutdown_message()
        
        # Wait for thread to finish
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        
        # Remove PID file
        self.remove_pid_file()
        
        self.logger.info("Screenshot daemon stopped")

    def _daemon_loop(self):
        """Main daemon loop"""
        last_screenshot_time = 0
        last_web_screenshot_time = 0
        last_cleanup_time = 0
        last_health_check_time = 0
        
        while self.running:
            try:
                current_time = time.time()
                
                # Regular screenshots
                if current_time - last_screenshot_time >= self.interval:
                    self.take_screenshot()
                    last_screenshot_time = current_time
                
                # Web screenshots
                web_config = self.config.get("web_screenshots", {})
                if web_config.get("enabled", False):
                    web_interval = web_config.get("interval", 300)
                    if current_time - last_web_screenshot_time >= web_interval:
                        self.take_web_screenshots()
                        last_web_screenshot_time = current_time
                
                # Check scheduled web screenshots (every minute)
                if current_time - last_health_check_time >= 60:
                    self.check_scheduled_web_screenshots()
                    last_health_check_time = current_time
                
                # Cleanup old screenshots
                if (self.config.get("enable_cleanup", True) and 
                    current_time - last_cleanup_time >= self.config.get("cleanup_interval", 3600)):
                    self.cleanup_old_screenshots()
                    last_cleanup_time = current_time
                
                # Sleep for a short time to avoid busy waiting
                time.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error in daemon loop: {e}")
                if self.running:
                    time.sleep(5)  # Sleep longer on error

    def monitor_mode(self):
        """Interactive monitoring mode"""
        print("📊 Screenshot Daemon Monitor")
        print("=" * 30)
        print("Press Ctrl+C to exit")
        print()
        
        try:
            while True:
                # Clear screen
                os.system('clear' if os.name == 'posix' else 'cls')
                
                print("📊 Screenshot Daemon Monitor")
                print("=" * 30)
                print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print()
                
                # Show daemon status
                if os.path.exists(PID_FILE):
                    with open(PID_FILE, 'r') as f:
                        pid = int(f.read().strip())
                    try:
                        os.kill(pid, 0)
                        print(f"✅ Daemon Status: Running (PID: {pid})")
                    except ProcessLookupError:
                        print("❌ Daemon Status: Not Running (stale PID)")
                else:
                    print("❌ Daemon Status: Not Running")
                
                print(f"📁 Output Directory: {self.output_dir}")
                print(f"📸 Active Regions: {', '.join(self.active_regions)}")
                print(f"⏱️ Screenshot Interval: {self.interval} seconds")
                print()
                
                # Show file statistics
                if self.output_dir.exists():
                    patterns = [f"{region_name}_*.png" for region_name in self.regions.keys()]
                    patterns.extend(["screenshot_*.png", "web_*.png", "scheduled_*.png"])
                    
                    all_files = []
                    for pattern in patterns:
                        all_files.extend(self.output_dir.glob(pattern))
                    
                    if all_files:
                        all_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                        total_size = sum(f.stat().st_size for f in all_files)
                        
                        print(f"📈 Statistics:")
                        print(f"  Total Files: {len(all_files)}")
                        print(f"  Total Size: {total_size / (1024*1024):.1f} MB")
                        print(f"  Oldest: {datetime.fromtimestamp(all_files[-1].stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
                        print(f"  Newest: {datetime.fromtimestamp(all_files[0].stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
                        print()
                        
                        print("📋 Recent Files:")
                        for i, file_path in enumerate(all_files[:5]):
                            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                            size = file_path.stat().st_size
                            print(f"  {i+1}. {file_path.name} ({size} bytes) - {mtime.strftime('%H:%M:%S')}")
                    else:
                        print("📋 No screenshots found")
                
                print("\n⏰ Next refresh in 5 seconds...")
                time.sleep(5)
                
        except KeyboardInterrupt:
            print("\n👋 Monitoring stopped")

    def cleanup_old_screenshots(self):
        """Clean up old screenshots based on age and count"""
        try:
            current_time = time.time()
            cutoff_time = current_time - (self.config["keep_days"] * 24 * 60 * 60)
            
            deleted_count = 0
            # Include all patterns
            patterns = [f"{region_name}_*.png" for region_name in self.regions.keys()]
            patterns.extend(["screenshot_*.png", "web_*.png", "scheduled_*.png"])
            
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
            self.logger.error(f"Error during cleanup: {e}")

# Keep the original ScreenshotManager for backward compatibility
class ScreenshotManager:
    def __init__(self, output_dir, regions, active_regions):
        self.output_dir = Path(output_dir)
        self.regions = regions
        self.active_regions = active_regions
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
        self.logger = logging.getLogger(__name__)
    
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
            patterns.append("web_*.png")  # Web screenshot pattern
            
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

class WebScreenshot:
    """Web screenshot handler using Selenium WebDriver"""
    
    def __init__(self, browser='firefox', headless=True, window_size=(1920, 1080)):
        self.browser = browser.lower()
        self.headless = headless
        self.window_size = window_size
        self.driver = None
        self.logger = logging.getLogger(__name__)
    
    def _setup_firefox_driver(self):
        """Setup Firefox WebDriver with headless options"""
        try:
            from selenium.webdriver.firefox.service import Service as FirefoxService
            
            options = FirefoxOptions()
            if self.headless:
                options.add_argument('--headless')
            
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size={},{}'.format(*self.window_size))
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-plugins')
            options.add_argument('--disable-images')  # Faster loading
            
            # Set viewport size for consistent screenshots
            options.set_preference('browser.window.width', self.window_size[0])
            options.set_preference('browser.window.height', self.window_size[1])
            
            # Disable full-page screenshot to get viewport-only
            options.set_preference('dom.webdriver.enabled', False)
            options.set_preference('useAutomationExtension', False)
            
            # Try to find system geckodriver
            try:
                # Check if geckodriver is in PATH
                import subprocess
                result = subprocess.run(['which', 'geckodriver'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    geckodriver_path = result.stdout.strip()
                    service = FirefoxService(geckodriver_path)
                    self.logger.info(f"Using system geckodriver: {geckodriver_path}")
                    return webdriver.Firefox(service=service, options=options)
                else:
                    self.logger.info("geckodriver not found in PATH, trying default")
            except Exception as e:
                self.logger.warning(f"Error finding geckodriver: {e}")
            
            # Fallback: try without custom service
            try:
                return webdriver.Firefox(options=options)
            except Exception as fallback_error:
                self.logger.error(f"Firefox fallback error: {fallback_error}")
                return None
            
        except Exception as e:
            self.logger.error(f"Failed to setup Firefox driver: {e}")
            return None
    
    def _setup_chrome_driver(self):
        """Setup Chrome WebDriver with headless options"""
        try:
            from selenium.webdriver.chrome.service import Service as ChromeService
            
            options = ChromeOptions()
            if self.headless:
                options.add_argument('--headless')
            
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size={},{}'.format(*self.window_size))
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-plugins')
            options.add_argument('--disable-images')  # Faster loading
            options.add_argument('--disable-web-security')
            options.add_argument('--disable-features=VizDisplayCompositor')
            
            # Set viewport size for consistent screenshots
            options.add_argument(f'--window-size={self.window_size[0]},{self.window_size[1]}')
            
            # Disable full-page screenshot to get viewport-only
            options.add_experimental_option('useAutomationExtension', False)
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            
            # Try to find system chromedriver
            try:
                # Check if chromedriver is in PATH
                import subprocess
                result = subprocess.run(['which', 'chromedriver'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    chromedriver_path = result.stdout.strip()
                    service = ChromeService(chromedriver_path)
                    self.logger.info(f"Using system chromedriver: {chromedriver_path}")
                    return webdriver.Chrome(service=service, options=options)
                else:
                    self.logger.info("chromedriver not found in PATH, trying default")
            except Exception as e:
                self.logger.warning(f"Error finding chromedriver: {e}")
            
            # Fallback: try without custom service
            try:
                return webdriver.Chrome(options=options)
            except Exception as fallback_error:
                self.logger.error(f"Chrome fallback error: {fallback_error}")
                return None
            
        except Exception as e:
            self.logger.error(f"Failed to setup Chrome driver: {e}")
            return None
    
    def start_driver(self):
        """Initialize WebDriver"""
        if self.browser == 'firefox':
            self.driver = self._setup_firefox_driver()
        elif self.browser == 'chrome':
            self.driver = self._setup_chrome_driver()
        else:
            self.logger.error(f"Unsupported browser: {self.browser}")
            return False
        
        if self.driver:
            self.logger.info(f"✅ {self.browser.title()} WebDriver started successfully")
            return True
        else:
            self.logger.error(f"❌ Failed to start {self.browser} WebDriver")
            return False
    
    def stop_driver(self):
        """Stop WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info(f"✅ {self.browser.title()} WebDriver stopped")
            except Exception as e:
                self.logger.error(f"Error stopping WebDriver: {e}")
            finally:
                self.driver = None
