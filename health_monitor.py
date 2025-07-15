#!/usr/bin/env python3
"""
Screenshot Daemon Health Monitor
===============================

This script monitors the screenshot daemon health and sends alerts if needed.
"""

import os
import sys
import time
import json
import smtplib
from datetime import datetime, timedelta
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configuration
MONITOR_CONFIG = {
    "screenshot_dir": "/Users/primetech/Documents/ss/screenshots",
    "max_age_minutes": 10,  # Alert if no screenshot in last 10 minutes
    "min_file_size": 1000,  # Alert if file size is too small
    "disk_space_threshold": 100,  # Alert if less than 100MB free
    "email_alerts": False,
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "email_from": "alerts@yourserver.com",
    "email_to": "admin@yourserver.com",
    "email_password": "your_password"
}

class ScreenshotHealthMonitor:
    def __init__(self, config):
        self.config = config
        self.screenshot_dir = Path(config["screenshot_dir"])
        self.alerts = []
    
    def check_recent_screenshots(self):
        """Check if recent screenshots exist"""
        if not self.screenshot_dir.exists():
            self.alerts.append("❌ Screenshot directory does not exist")
            return False
        
        # Find most recent screenshot
        screenshots = list(self.screenshot_dir.glob("screenshot_*.png"))
        if not screenshots:
            self.alerts.append("❌ No screenshots found")
            return False
        
        # Check most recent screenshot
        latest = max(screenshots, key=lambda x: x.stat().st_mtime)
        latest_time = datetime.fromtimestamp(latest.stat().st_mtime)
        age_minutes = (datetime.now() - latest_time).total_seconds() / 60
        
        if age_minutes > self.config["max_age_minutes"]:
            self.alerts.append(f"⚠️ Last screenshot is {age_minutes:.1f} minutes old")
            return False
        
        # Check file size
        file_size = latest.stat().st_size
        if file_size < self.config["min_file_size"]:
            self.alerts.append(f"⚠️ Screenshot file size is too small: {file_size} bytes")
            return False
        
        return True
    
    def check_disk_space(self):
        """Check available disk space"""
        if not self.screenshot_dir.exists():
            return False
        
        disk_usage = os.statvfs(self.screenshot_dir)
        free_space = disk_usage.f_frsize * disk_usage.f_bavail
        free_space_mb = free_space / (1024 * 1024)
        
        if free_space_mb < self.config["disk_space_threshold"]:
            self.alerts.append(f"⚠️ Low disk space: {free_space_mb:.1f} MB free")
            return False
        
        return True
    
    def check_daemon_process(self):
        """Check if daemon process is running"""
        pid_file = "/Users/primetech/Documents/ss/screenshot-daemon.pid"
        
        if not os.path.exists(pid_file):
            self.alerts.append("❌ Daemon PID file not found")
            return False
        
        try:
            with open(pid_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process exists
            os.kill(pid, 0)
            return True
            
        except (ProcessLookupError, ValueError):
            self.alerts.append("❌ Daemon process is not running")
            return False
    
    def get_statistics(self):
        """Get screenshot statistics"""
        if not self.screenshot_dir.exists():
            return {}
        
        screenshots = list(self.screenshot_dir.glob("screenshot_*.png"))
        if not screenshots:
            return {}
        
        # Calculate statistics
        total_size = sum(f.stat().st_size for f in screenshots)
        oldest = min(screenshots, key=lambda x: x.stat().st_mtime)
        newest = max(screenshots, key=lambda x: x.stat().st_mtime)
        
        return {
            "total_files": len(screenshots),
            "total_size_mb": total_size / (1024 * 1024),
            "oldest_file": oldest.name,
            "newest_file": newest.name,
            "oldest_time": datetime.fromtimestamp(oldest.stat().st_mtime),
            "newest_time": datetime.fromtimestamp(newest.stat().st_mtime)
        }
    
    def send_email_alert(self, subject, body):
        """Send email alert"""
        if not self.config["email_alerts"]:
            return
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.config["email_from"]
            msg['To'] = self.config["email_to"]
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(self.config["smtp_server"], self.config["smtp_port"])
            server.starttls()
            server.login(self.config["email_from"], self.config["email_password"])
            
            server.send_message(msg)
            server.quit()
            
            print(f"✅ Email alert sent: {subject}")
            
        except Exception as e:
            print(f"❌ Failed to send email alert: {e}")
    
    def run_health_check(self):
        """Run complete health check"""
        print("🏥 Screenshot Daemon Health Check")
        print("=" * 35)
        print(f"Time: {datetime.now()}")
        print()
        
        # Clear previous alerts
        self.alerts = []
        
        # Run checks
        recent_ok = self.check_recent_screenshots()
        disk_ok = self.check_disk_space()
        daemon_ok = self.check_daemon_process()
        
        # Get statistics
        stats = self.get_statistics()
        
        # Display results
        print("📊 Health Check Results:")
        print(f"  Recent Screenshots: {'✅' if recent_ok else '❌'}")
        print(f"  Disk Space: {'✅' if disk_ok else '❌'}")
        print(f"  Daemon Process: {'✅' if daemon_ok else '❌'}")
        print()
        
        if stats:
            print("📈 Statistics:")
            print(f"  Total Files: {stats['total_files']}")
            print(f"  Total Size: {stats['total_size_mb']:.1f} MB")
            print(f"  Oldest: {stats['oldest_file']} ({stats['oldest_time']})")
            print(f"  Newest: {stats['newest_file']} ({stats['newest_time']})")
            print()
        
        # Show alerts
        if self.alerts:
            print("🚨 Alerts:")
            for alert in self.alerts:
                print(f"  {alert}")
            print()
            
            # Send email alert if configured
            if self.config["email_alerts"]:
                subject = "Screenshot Daemon Health Alert"
                body = f"Screenshot daemon health check failed:\n\n" + "\n".join(self.alerts)
                self.send_email_alert(subject, body)
        
        # Overall status
        overall_status = recent_ok and disk_ok and daemon_ok
        print(f"🎯 Overall Status: {'✅ HEALTHY' if overall_status else '❌ UNHEALTHY'}")
        
        return overall_status
    
    def continuous_monitoring(self, interval=300):
        """Run continuous monitoring"""
        print(f"🔄 Starting continuous monitoring (every {interval} seconds)")
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                self.run_health_check()
                print(f"\n⏰ Next check in {interval} seconds...")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n👋 Monitoring stopped")

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Screenshot Daemon Health Monitor')
    parser.add_argument('--continuous', '-c', action='store_true',
                       help='Run continuous monitoring')
    parser.add_argument('--interval', '-i', type=int, default=300,
                       help='Monitoring interval in seconds (default: 300)')
    parser.add_argument('--config', help='Configuration file path')
    
    args = parser.parse_args()
    
    # Load configuration
    config = MONITOR_CONFIG.copy()
    if args.config and os.path.exists(args.config):
        with open(args.config, 'r') as f:
            config.update(json.load(f))
    
    # Create monitor
    monitor = ScreenshotHealthMonitor(config)
    
    # Run monitoring
    if args.continuous:
        monitor.continuous_monitoring(args.interval)
    else:
        status = monitor.run_health_check()
        sys.exit(0 if status else 1)

if __name__ == "__main__":
    main()
