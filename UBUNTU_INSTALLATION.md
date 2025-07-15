# Ubuntu Server Installation Guide

Bu rehber, screenshot daemon'unu Ubuntu/Debian sunucusunda çalıştırmak için gerekli tüm bağımlılıkları kurmak için terminal komutlarını içerir.

## 1. Sistem Güncellemesi

```bash
# Sistem paket listesini güncelle
sudo apt update

# Sistem paketlerini güncelle
sudo apt upgrade -y
```

## 2. Python ve Pip Kurulumu

```bash
# Python 3 ve pip kurulumu
sudo apt install -y python3 python3-pip python3-venv

# Python versiyonunu kontrol et
python3 --version
pip3 --version
```

## 3. Headless Grafik Sistemi (Xvfb) Kurulumu

```bash
# Xvfb ve gerekli X11 paketlerini kur
sudo apt install -y xvfb x11-utils xauth

# Ek grafik kütüphaneleri
sudo apt install -y libx11-dev libxext-dev libxrender-dev libxtst-dev

# Font desteği için
sudo apt install -y fonts-liberation fonts-dejavu-core
```

## 4. Python Bağımlılıkları için Sistem Paketleri

```bash
# PIL/Pillow için gerekli kütüphaneler
sudo apt install -y libjpeg-dev libpng-dev libtiff-dev libfreetype6-dev

# Tkinter desteği (pyautogui için)
sudo apt install -y python3-tk

# Scrot (screenshot alternatifi)
sudo apt install -y scrot

# PyAutoGUI için ek bağımlılıklar
sudo apt install -y python3-dev libffi-dev

# OpenCV bağımlılıkları (opsiyonel)
sudo apt install -y libopencv-dev python3-opencv

# Firefox (web screenshot için)
sudo apt install -y firefox

# Chromium (Firefox alternatifi)
sudo apt install -y chromium-browser

# XDG Utils (Firefox için)
sudo apt install -y xdg-utils

# GeckoDriver (Firefox için WebDriver) - Manuel kurulum
wget -q -O /tmp/geckodriver.tar.gz https://github.com/mozilla/geckodriver/releases/download/v0.33.0/geckodriver-v0.33.0-linux64.tar.gz
sudo tar -xzf /tmp/geckodriver.tar.gz -C /usr/local/bin/
sudo chmod +x /usr/local/bin/geckodriver
rm /tmp/geckodriver.tar.gz

# gnome-screenshot (pyautogui için)
sudo apt install -y gnome-screenshot
```

## 5. Python Sanal Ortam Oluşturma

```bash
# Proje dizinine git
cd /path/to/your/project

# Sanal ortam oluştur
python3 -m venv venv

# Sanal ortamı aktifleştir
source venv/bin/activate

# Pip'i güncelle
pip install --upgrade pip
```

## 6. Python Paketlerini Kurma

```bash
# requirements.txt dosyasındaki paketleri kur
pip install -r requirements.txt

# Veya manuel olarak:
pip install pyautogui Pillow requests

# Web screenshot için ek paketler (webdriver-manager opsiyonel)
pip install selenium
```

## 7. Servis Kurulumu (Systemd)

```bash
# Servis dosyasını sistem dizinine kopyala
sudo cp screenshot-daemon.service /etc/systemd/system/

# Servis dosyasını düzenle (gerekirse)
sudo nano /etc/systemd/system/screenshot-daemon.service

# Systemd'yi yeniden yükle
sudo systemctl daemon-reload

# Servisi etkinleştir
sudo systemctl enable screenshot-daemon

# Servisi başlat
sudo systemctl start screenshot-daemon
```

## 8. Güvenlik Duvarı Ayarları (Opsiyonel)

```bash
# UFW güvenlik duvarı kurulumu
sudo apt install -y ufw

# Temel kurallar
sudo ufw default deny incoming
sudo ufw default allow outgoing

# SSH erişimi (dikkatli olun!)
sudo ufw allow ssh

# Güvenlik duvarını etkinleştir
sudo ufw enable
```

## 9. Test Komutları

```bash
# Xvfb ile test screenshot
xvfb-run -a python3 screenshot_cron.py single

# Servis durumunu kontrol et
sudo systemctl status screenshot-daemon

# Log dosyalarını kontrol et
sudo journalctl -u screenshot-daemon -f

# Manuel test
xvfb-run -a -s "-screen 0 1920x1080x24" python3 screenshot_cron.py single
```

## 10. Tam Kurulum Scripti

Tüm adımları tek seferde çalıştırmak için:

```bash
#!/bin/bash
# Ubuntu Screenshot Daemon Full Installation Script

echo "🚀 Ubuntu Screenshot Daemon Installation Starting..."

# 1. Sistem güncellemesi
echo "📦 Updating system packages..."
sudo apt update -y
sudo apt upgrade -y

# 2. Python kurulumu
echo "🐍 Installing Python and pip..."
sudo apt install -y python3 python3-pip python3-venv python3-dev

# 3. Xvfb ve X11 kurulumu
echo "🖥️ Installing headless display server (Xvfb)..."
sudo apt install -y xvfb x11-utils xauth libx11-dev libxext-dev libxrender-dev libxtst-dev

# 4. Grafik kütüphaneleri
echo "🎨 Installing graphics libraries..."
sudo apt install -y libjpeg-dev libpng-dev libtiff-dev libfreetype6-dev

# 5. Tkinter ve ek paketler
echo "🔧 Installing additional packages..."
sudo apt install -y python3-tk scrot fonts-liberation fonts-dejavu-core

# 6. Firefox ve GeckoDriver
echo "🦊 Installing Firefox and GeckoDriver..."
sudo apt install -y firefox
wget -q -O /tmp/geckodriver.tar.gz https://github.com/mozilla/geckodriver/releases/download/v0.33.0/geckodriver-v0.33.0-linux64.tar.gz
sudo tar -xzf /tmp/geckodriver.tar.gz -C /usr/local/bin/
sudo chmod +x /usr/local/bin/geckodriver
rm /tmp/geckodriver.tar.gz

# 7. Python sanal ortam
echo "🌐 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# 8. Python paketleri
echo "📚 Installing Python packages..."
pip install --upgrade pip
pip install pyautogui Pillow requests

# 9. Test
echo "✅ Testing installation..."
xvfb-run -a python3 screenshot_cron.py single --regions full_screen

echo "🎉 Installation completed!"
echo "💡 Usage: xvfb-run -a python3 screenshot_cron.py start"
```

## Önemli Notlar

### Headless Çalıştırma
```bash
# Her zaman xvfb-run ile çalıştırın
xvfb-run -a python3 screenshot_cron.py start

# Belirli ekran boyutu ile
xvfb-run -a -s "-screen 0 1920x1080x24" python3 screenshot_cron.py start
```

### Güvenlik
- Root kullanıcısı yerine ayrı bir kullanıcı hesabı kullanın
- Telegram bot token'ınızı güvenli tutun
- Sadece gerekli portları açın

### Performans
- Düşük screenshot interval'ı (< 10 saniye) yüksek CPU kullanımına neden olabilir
- Disk alanını düzenli olarak kontrol edin
- Log dosyalarını döndürün

### Sorun Giderme
```bash
# Servisi yeniden başlat
sudo systemctl restart screenshot-daemon

# Detaylı log
sudo journalctl -u screenshot-daemon -f --no-pager

# Manuel debug
xvfb-run -a python3 screenshot_cron.py monitor
```

Bu kurulum rehberi, Ubuntu 18.04+ ve Debian 10+ sistemlerde test edilmiştir.
