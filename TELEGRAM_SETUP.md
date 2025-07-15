# Telegram Bot Setup Guide

## 📱 Telegram Bot Kurulumu

### 1. Bot Oluşturma
1. Telegram'da @BotFather'a gidin
2. `/start` komutunu gönderin
3. `/newbot` komutunu gönderin
4. Bot adını girin (örn: "Screenshot Monitor Bot")
5. Bot kullanıcı adını girin (örn: "screenshot_monitor_bot")
6. Bot token'ını kaydedin

### 2. Grup Oluşturma ve Bot Ekleme
Her bölge için ayrı grup oluşturun:

- **full_screen** → "Full Screen Screenshots"
- **top_left** → "Top Left Screenshots"
- **top_right** → "Top Right Screenshots"
- **bottom_left** → "Bottom Left Screenshots"
- **bottom_right** → "Bottom Right Screenshots"
- **center** → "Center Screenshots"
- **taskbar** → "Taskbar Screenshots"
- **header** → "Header Screenshots"
- **custom** → "Custom Screenshots"

### 3. Chat ID Alma
1. Botunuzu gruplara ekleyin
2. @userinfobot'u gruplara ekleyin
3. `/start` komutunu gönderin
4. Chat ID'yi kaydedin (örn: -1001234567890)

### 4. Konfigürasyon Güncelleme

```python
# screenshot_cron.py dosyasındaki CONFIG'i güncelleyin
"telegram": {
    "enabled": True,
    "bot_token": "1234567890:ABCdefGHIjklMNOpqrSTUvwxyz",  # Gerçek token
    "region_chats": {
        "full_screen": "-1001234567890",     # Gerçek chat ID
        "top_left": "-1001234567891",
        "top_right": "-1001234567892", 
        "bottom_left": "-1001234567893",
        "bottom_right": "-1001234567894",
        "center": "-1001234567895",
        "taskbar": "-1001234567896",
        "header": "-1001234567897",
        "custom": "-1001234567898"
    },
    "send_immediately": True,
    "message_template": "🖥️ Screenshot: {region_name}\n📅 Time: {timestamp}\n📏 Size: {file_size} bytes"
}
```

### 5. Test Etme

```bash
# Telegram konfigürasyonunu görüntüle
python3 screenshot_cron.py telegram

# Bot bağlantısını test et
python3 screenshot_cron.py telegram --test-telegram

# Tek screenshot gönder
python3 screenshot_cron.py single --regions "full_screen"

# Daemon başlat
python3 screenshot_cron.py start --regions "top_left,center"
```

## 🔧 Gelişmiş Ayarlar

### Mesaj Şablonu Özelleştirme
```python
"message_template": "🖥️ {region_name} Screenshot\n📅 {timestamp}\n📏 {file_size} bytes\n🖥️ Server: MyServer"
```

### Retry Ayarları
```python
"retry_attempts": 3,    # Başarısız olunca kaç kez tekrar dene
"retry_delay": 5        # Denemeler arası bekleme süresi
```

### Özel Bölge Ekleme
```bash
# Yeni bölge ekle
python3 screenshot_cron.py start --add-region "my_app:100,200,800,600"

# Telegram chat ID'sini manuel olarak config'e ekle
"my_app": "-1001234567899"
```

## 🚨 Sorun Giderme

### Bot Token Hataları
- Token'ın doğru olduğundan emin olun
- Bot'un aktif olduğundan emin olun

### Chat ID Hataları
- Chat ID'nin doğru olduğundan emin olun
- Bot'un gruplarda admin olduğundan emin olun

### Mesaj Gönderme Hataları
- Bot'un mesaj gönderme iznine sahip olduğundan emin olun
- Grup ayarlarını kontrol edin

## 📊 Monitoring

```bash
# Daemon durumunu kontrol et
python3 screenshot_cron.py status

# Canlı monitoring
python3 screenshot_cron.py monitor

# Telegram istatistiklerini görüntüle
python3 screenshot_cron.py config | grep -A 20 telegram
```

## 🎯 Örnek Kullanım

```bash
# Sadece merkez bölgeyi Telegram'a gönder
python3 screenshot_cron.py start --regions "center" --bot-token "YOUR_TOKEN"

# Tüm bölgeleri 30 saniye aralıklarla gönder
python3 screenshot_cron.py start --regions "full_screen,top_left,top_right,bottom_left,bottom_right" --interval 30

# Özel bölge ekle ve gönder
python3 screenshot_cron.py start --add-region "taskbar:0,1040,1920,80" --regions "taskbar"
```
