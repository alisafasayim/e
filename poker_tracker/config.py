"""
POKER TRACKER - CONFIGURATION
==============================
Ekran bölgeleri, OCR ayarları ve overlay konfigürasyonu.
"""

from dataclasses import dataclass, field
from typing import Tuple, Dict, Optional
import json
import os


@dataclass
class ScreenRegion:
    """Ekranda bir dikdörtgen bölge."""
    x: int
    y: int
    width: int
    height: int

    @property
    def bbox(self) -> Tuple[int, int, int, int]:
        """mss uyumlu bbox (left, top, right, bottom)."""
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    @property
    def as_dict(self) -> dict:
        """mss monitor format."""
        return {"left": self.x, "top": self.y, "width": self.width, "height": self.height}


@dataclass
class TableLayout:
    """
    Poker masası ekran düzeni.
    Tüm bölgeler piksel koordinatları olarak tanımlanır.
    Kullanıcı kendi poker istemcisine göre ayarlamalıdır.
    """
    # Masa penceresi
    table_window: ScreenRegion = field(default_factory=lambda: ScreenRegion(0, 0, 1920, 1080))

    # Board kartları (5 kart yeri)
    board_cards: list = field(default_factory=lambda: [
        ScreenRegion(710, 340, 70, 95),   # Flop 1
        ScreenRegion(790, 340, 70, 95),   # Flop 2
        ScreenRegion(870, 340, 70, 95),   # Flop 3
        ScreenRegion(950, 340, 70, 95),   # Turn
        ScreenRegion(1030, 340, 70, 95),  # River
    ])

    # Hero kartları (2 kart)
    hero_cards: list = field(default_factory=lambda: [
        ScreenRegion(870, 620, 70, 95),   # Kart 1
        ScreenRegion(950, 620, 70, 95),   # Kart 2
    ])

    # Pot bölgesi
    pot_region: ScreenRegion = field(default_factory=lambda: ScreenRegion(830, 290, 200, 40))

    # Bet bölgeleri (6 oyuncu pozisyonu için)
    bet_regions: list = field(default_factory=lambda: [
        ScreenRegion(820, 480, 120, 30),   # Seat 1 (Hero)
        ScreenRegion(1200, 420, 120, 30),  # Seat 2
        ScreenRegion(1200, 280, 120, 30),  # Seat 3
        ScreenRegion(820, 220, 120, 30),   # Seat 4
        ScreenRegion(440, 280, 120, 30),   # Seat 5
        ScreenRegion(440, 420, 120, 30),   # Seat 6
    ])

    # Oyuncu isimleri / stack bilgileri
    player_name_regions: list = field(default_factory=lambda: [
        ScreenRegion(830, 590, 160, 25),   # Seat 1 (Hero)
        ScreenRegion(1220, 480, 160, 25),  # Seat 2
        ScreenRegion(1220, 230, 160, 25),  # Seat 3
        ScreenRegion(830, 180, 160, 25),   # Seat 4
        ScreenRegion(420, 230, 160, 25),   # Seat 5
        ScreenRegion(420, 480, 160, 25),   # Seat 6
    ])

    # Stack bilgileri
    stack_regions: list = field(default_factory=lambda: [
        ScreenRegion(830, 615, 160, 25),   # Seat 1 (Hero)
        ScreenRegion(1220, 505, 160, 25),  # Seat 2
        ScreenRegion(1220, 255, 160, 25),  # Seat 3
        ScreenRegion(830, 205, 160, 25),   # Seat 4
        ScreenRegion(420, 255, 160, 25),   # Seat 5
        ScreenRegion(420, 505, 160, 25),   # Seat 6
    ])

    # Dealer button bölgesi
    dealer_button_regions: list = field(default_factory=lambda: [
        ScreenRegion(810, 570, 30, 30),    # Seat 1
        ScreenRegion(1190, 460, 30, 30),   # Seat 2
        ScreenRegion(1190, 260, 30, 30),   # Seat 3
        ScreenRegion(810, 200, 30, 30),    # Seat 4
        ScreenRegion(440, 260, 30, 30),    # Seat 5
        ScreenRegion(440, 460, 30, 30),    # Seat 6
    ])

    # Aksiyon butonları bölgesi (fold/check/call/raise varlığı)
    action_buttons_region: ScreenRegion = field(
        default_factory=lambda: ScreenRegion(650, 750, 600, 60)
    )


@dataclass
class OCRConfig:
    """OCR motoru ayarları."""
    # Tesseract ayarları
    tesseract_cmd: str = "tesseract"
    lang: str = "eng"
    psm: int = 7  # Single line mode
    oem: int = 3  # LSTM + Legacy

    # Ön işleme
    threshold_value: int = 127
    invert_colors: bool = True
    scale_factor: float = 2.0  # Büyütme faktörü

    # EasyOCR ayarları
    use_easyocr: bool = False
    easyocr_languages: list = field(default_factory=lambda: ["en"])
    easyocr_gpu: bool = False


@dataclass
class OverlayConfig:
    """Overlay pencere ayarları."""
    # Pozisyon ve boyut
    x: int = 10
    y: int = 10
    width: int = 400
    height: int = 600

    # Görünüm
    bg_color: str = "#1a1a2e"
    text_color: str = "#e0e0e0"
    accent_color: str = "#00d4ff"
    warning_color: str = "#ff6b6b"
    success_color: str = "#51cf66"
    font_family: str = "Consolas"
    font_size: int = 11
    title_font_size: int = 14
    opacity: float = 0.88

    # Güncelleme
    refresh_rate_ms: int = 500  # Overlay yenileme hızı


@dataclass
class TrackerConfig:
    """Ana tracker konfigürasyonu."""
    # Genel
    scan_interval: float = 0.5      # Ekran tarama aralığı (saniye)
    hero_seat: int = 0              # Hero'nun oturduğu koltuk (0-5)
    num_seats: int = 6              # Masa koltuk sayısı

    # Blind seviyeleri
    small_blind: float = 0.5
    big_blind: float = 1.0

    # Modüller
    table_layout: TableLayout = field(default_factory=TableLayout)
    ocr_config: OCRConfig = field(default_factory=OCRConfig)
    overlay_config: OverlayConfig = field(default_factory=OverlayConfig)

    # Debug
    debug_mode: bool = False
    save_screenshots: bool = False
    screenshot_dir: str = "debug_screenshots"

    def save_to_file(self, filepath: str) -> None:
        """Konfigürasyonu JSON dosyasına kaydet."""
        import dataclasses

        def _to_dict(obj):
            if dataclasses.is_dataclass(obj):
                return {k: _to_dict(v) for k, v in dataclasses.asdict(obj).items()}
            if isinstance(obj, list):
                return [_to_dict(i) for i in obj]
            return obj

        with open(filepath, "w") as f:
            json.dump(_to_dict(self), f, indent=2)

    @classmethod
    def load_from_file(cls, filepath: str) -> "TrackerConfig":
        """JSON dosyasından konfigürasyon yükle."""
        if not os.path.exists(filepath):
            return cls()

        with open(filepath, "r") as f:
            data = json.load(f)

        config = cls()
        if "small_blind" in data:
            config.small_blind = data["small_blind"]
        if "big_blind" in data:
            config.big_blind = data["big_blind"]
        if "hero_seat" in data:
            config.hero_seat = data["hero_seat"]
        if "scan_interval" in data:
            config.scan_interval = data["scan_interval"]
        if "debug_mode" in data:
            config.debug_mode = data["debug_mode"]

        return config
