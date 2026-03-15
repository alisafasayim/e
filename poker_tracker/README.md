# Poker Tracker Agent - Canlı Poker Overlay Sistemi

Online poker oyunlarını canlı takip ederek ekran üzerine bilgi yazan ajan sistemi.

## Özellikler

- **Ekran Yakalama**: Poker masasını gerçek zamanlı olarak yakalar
- **Kart Tanıma**: OpenCV ile board ve hero kartlarını otomatik tanır
- **OCR Metin Okuma**: Pot miktarı, bet tutarları ve stack bilgilerini okur
- **Pozisyon Takibi**: Dealer button'ı algılayarak pozisyonları hesaplar
- **Strateji Önerileri**: GTO bazlı preflop/postflop öneriler sunar
- **Overlay Ekran**: Yarı-saydam, sürüklenebilir bilgi paneli
- **Konsol Modu**: GUI olmadan terminal çıktısı

## Mimari

```
poker_tracker/
├── main.py              # Ana giriş noktası ve ajan döngüsü
├── config.py            # Ekran bölgeleri ve ayarlar
├── screen_capture.py    # mss ile ekran yakalama
├── card_detector.py     # OpenCV ile kart tanıma
├── ocr_engine.py        # Tesseract/EasyOCR ile metin okuma
├── game_state_tracker.py # Oyun durumu takipçisi
├── advisor.py           # Strateji danışmanı (poker_bot_v4 entegrasyonu)
├── overlay.py           # Tkinter overlay penceresi
└── requirements.txt     # Python bağımlılıkları
```

## Kurulum

```bash
# 1. Bağımlılıkları kur
pip install -r poker_tracker/requirements.txt

# 2. Tesseract OCR kur (sistem paketi)
# Ubuntu/Debian:
sudo apt install tesseract-ocr
# macOS:
brew install tesseract
# Windows: https://github.com/tesseract-ocr/tesseract adresinden indir
```

## Kullanım

```bash
# Varsayılan modda başlat (GUI overlay)
python poker_tracker/main.py

# Terminal modunda başlat
python poker_tracker/main.py --console

# Ekran kalibrasyonu (ilk kurulumda çalıştırın)
python poker_tracker/main.py --calibrate

# Özel konfigürasyon ile
python poker_tracker/main.py --config config.json --sb 1 --bb 2 --seat 0

# Debug modunda
python poker_tracker/main.py --debug

# Test modu (ekran yakalama olmadan)
python poker_tracker/main.py --mock --console
```

## İlk Kurulum

1. Önce kalibrasyon modunu çalıştırarak poker masanızın ekran bölgelerini ayarlayın:
   ```bash
   python poker_tracker/main.py --calibrate
   ```

2. Poker istemcinizi açın ve masaya oturun

3. Tracker'ı başlatın:
   ```bash
   python poker_tracker/main.py --config poker_tracker_config.json
   ```

## Overlay Bilgileri

Overlay ekranda şu bilgileri gösterir:

| Alan | Açıklama |
|------|----------|
| **El/Sokak/Pot** | Anlık oyun durumu |
| **ÖNERİ** | FOLD/CHECK/CALL/BET/RAISE önerisi |
| **El Gücü** | Equity, hand category, güç etiketi |
| **Board** | Texture analizi, tehlike seviyesi (0-10 bar) |
| **Draw** | Draw tipi ve out sayısı |
| **Reasoning** | Pozisyon, equity, pot odds, SPR detayları |

## Ekran Bölgeleri Yapısı

```
┌────────────────────────────────────────┐
│              Poker Masası               │
│                                         │
│      [P4]     [P5]     [P6]           │
│                                         │
│  [Bet4]   ┌─────────────┐  [Bet6]     │
│            │  Board Cards │             │
│  [P3]     │ [F1][F2][F3] │   [P1]     │
│            │   [T] [R]   │             │
│  [Bet3]   │   POT: $XX  │  [Bet1]     │
│            └─────────────┘             │
│      [P2]    [Hero Cards]   [P1]      │
│              [H1] [H2]                 │
│         [Action Buttons]               │
└────────────────────────────────────────┘
```

## Kısayollar

- **ESC**: Programı kapat
- **Sürükle**: Overlay penceresini taşı
- **Ctrl+C**: Terminal'den durdur

## Strateji Motoru

poker_bot_v4 modüllerini kullanarak:
- Preflop: GTO bazlı RFI, 3-bet ve defense range'leri
- Postflop: Board texture, SPR ve equity bazlı karar motoru
- Bet sizing: Dinamik, rakip tipine göre ayarlanan boyutlandırma
