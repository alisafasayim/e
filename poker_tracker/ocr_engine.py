"""
POKER TRACKER - OCR ENGINE
===========================
Metin tanıma modülü.
Pot miktarı, bet tutarları, stack bilgileri ve oyuncu isimlerini okur.
"""

import logging
import re
from typing import Optional, Tuple, List

import numpy as np

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

from config import OCRConfig

log = logging.getLogger("OCREngine")


class OCREngine:
    """
    Poker masası OCR motoru.
    Tesseract veya EasyOCR ile metin tanıma.
    """

    def __init__(self, config: Optional[OCRConfig] = None):
        self.config = config or OCRConfig()
        self._easyocr_reader = None

        if self.config.use_easyocr:
            if not EASYOCR_AVAILABLE:
                raise ImportError("easyocr gerekli: pip install easyocr")
            self._easyocr_reader = easyocr.Reader(
                self.config.easyocr_languages,
                gpu=self.config.easyocr_gpu
            )
        elif not TESSERACT_AVAILABLE:
            log.warning("pytesseract bulunamadı. pip install pytesseract")

    def read_text(self, image: np.ndarray) -> str:
        """
        Görüntüden metin okur.

        Args:
            image: BGR formatında görüntü

        Returns:
            Okunan metin
        """
        if image is None or image.size == 0:
            return ""

        # Ön işleme
        processed = self._preprocess_image(image)

        # OCR
        if self.config.use_easyocr and self._easyocr_reader:
            return self._read_with_easyocr(processed)
        elif TESSERACT_AVAILABLE:
            return self._read_with_tesseract(processed)
        else:
            log.error("OCR motoru bulunamadı!")
            return ""

    def read_amount(self, image: np.ndarray) -> Optional[float]:
        """
        Görüntüden para miktarı okur.
        '$12.50', '12.5', '1,250' gibi formatları destekler.

        Returns:
            float miktar veya None
        """
        text = self.read_text(image)
        return self._parse_amount(text)

    def read_pot(self, pot_image: np.ndarray) -> Optional[float]:
        """Pot miktarını okur."""
        amount = self.read_amount(pot_image)
        if amount is not None:
            log.debug(f"Pot: ${amount:.2f}")
        return amount

    def read_bet(self, bet_image: np.ndarray) -> Optional[float]:
        """Bir oyuncunun bet miktarını okur."""
        amount = self.read_amount(bet_image)
        if amount is not None:
            log.debug(f"Bet: ${amount:.2f}")
        return amount

    def read_stack(self, stack_image: np.ndarray) -> Optional[float]:
        """Bir oyuncunun stack miktarını okur."""
        return self.read_amount(stack_image)

    def read_player_name(self, name_image: np.ndarray) -> str:
        """Oyuncu ismini okur."""
        text = self.read_text(name_image)
        # Temizle
        name = text.strip()
        # Alfanümerik olmayan karakterleri kaldır (bazı harf/rakam bırak)
        name = re.sub(r'[^a-zA-Z0-9_\- ]', '', name)
        return name.strip()

    def read_card_rank(self, rank_image: np.ndarray) -> Optional[str]:
        """
        Kart rank bölgesinden rank okur.
        CardDetector'ın tanıyamadığı durumlarda kullanılır.
        """
        text = self.read_text(rank_image).strip().upper()

        # Doğrudan eşleştirme
        rank_map = {
            "2": "2", "3": "3", "4": "4", "5": "5", "6": "6",
            "7": "7", "8": "8", "9": "9", "10": "T",
            "J": "J", "Q": "Q", "K": "K", "A": "A",
            # OCR hataları için alternatifler
            "1O": "T", "IO": "T", "1D": "T",
            "0": "T",  # Bazen 10'u tek karakter olarak okur
        }

        return rank_map.get(text)

    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """OCR için görüntü ön işleme."""
        if not CV2_AVAILABLE:
            return image

        # Gri tonlamaya çevir
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Büyüt (küçük metinler için)
        if self.config.scale_factor != 1.0:
            gray = cv2.resize(
                gray, None,
                fx=self.config.scale_factor,
                fy=self.config.scale_factor,
                interpolation=cv2.INTER_CUBIC
            )

        # Kontrast artır
        gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)

        # Gaussian blur (gürültü azaltma)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)

        # Threshold (ikili görüntü)
        if self.config.invert_colors:
            _, binary = cv2.threshold(
                gray, self.config.threshold_value, 255, cv2.THRESH_BINARY_INV
            )
        else:
            _, binary = cv2.threshold(
                gray, self.config.threshold_value, 255, cv2.THRESH_BINARY
            )

        # Otsu threshold (adaptif)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        return binary

    def _read_with_tesseract(self, image: np.ndarray) -> str:
        """Tesseract ile metin oku."""
        config_str = (
            f"--psm {self.config.psm} "
            f"--oem {self.config.oem} "
            f"-c tessedit_char_whitelist=0123456789.$,kKmMBBAallIn "
        )
        try:
            text = pytesseract.image_to_string(
                image, lang=self.config.lang, config=config_str
            )
            return text.strip()
        except Exception as e:
            log.error(f"Tesseract hatası: {e}")
            return ""

    def _read_with_easyocr(self, image: np.ndarray) -> str:
        """EasyOCR ile metin oku."""
        try:
            results = self._easyocr_reader.readtext(image, detail=0)
            return " ".join(results).strip()
        except Exception as e:
            log.error(f"EasyOCR hatası: {e}")
            return ""

    def _parse_amount(self, text: str) -> Optional[float]:
        """
        Metin'den para miktarını çıkarır.

        Desteklenen formatlar:
        - '$12.50', '12.50', '$12,50'
        - '$1,250', '1250'
        - '1.2k', '1.2K' (kilo)
        - '1.5m', '1.5M' (milyon)
        - 'All-In', 'ALL IN'
        """
        if not text:
            return None

        text = text.strip()

        # All-in kontrolü
        if re.search(r'(?i)all[\s\-]?in', text):
            return -1.0  # Özel değer: all-in

        # Para sembollerini temizle
        text = text.replace('$', '').replace('€', '').replace('₺', '')

        # K/M çarpanları
        multiplier = 1.0
        if text.upper().endswith('K'):
            multiplier = 1000
            text = text[:-1]
        elif text.upper().endswith('M'):
            multiplier = 1000000
            text = text[:-1]
        elif text.upper().endswith('BB'):
            text = text[:-2]
            # BB cinsinden - daha sonra dönüştürülecek

        # Virgülü nokta yap
        text = text.replace(',', '.')

        # Birden fazla nokta varsa son haricindekileri kaldır
        parts = text.split('.')
        if len(parts) > 2:
            text = ''.join(parts[:-1]) + '.' + parts[-1]

        # Sadece rakam ve nokta bırak
        cleaned = re.sub(r'[^\d.]', '', text)

        if not cleaned:
            return None

        try:
            value = float(cleaned) * multiplier
            return value
        except ValueError:
            return None

    def detect_dealer_button(self, button_image: np.ndarray) -> bool:
        """
        Verilen bölgede dealer button var mı kontrol eder.
        Beyaz/sarı yuvarlak obje arar.
        """
        if not CV2_AVAILABLE or button_image is None or button_image.size == 0:
            return False

        hsv = cv2.cvtColor(button_image, cv2.COLOR_BGR2HSV)

        # Sarı/beyaz renk aralığı (dealer button)
        # Sarı
        yellow_lower = np.array([20, 80, 80])
        yellow_upper = np.array([40, 255, 255])
        yellow_mask = cv2.inRange(hsv, yellow_lower, yellow_upper)

        # Beyaz
        white_lower = np.array([0, 0, 200])
        white_upper = np.array([180, 30, 255])
        white_mask = cv2.inRange(hsv, white_lower, white_upper)

        combined = cv2.bitwise_or(yellow_mask, white_mask)
        ratio = np.sum(combined > 0) / combined.size

        # Yeterli sarı/beyaz alan varsa button var
        return ratio > 0.15

    def detect_action_buttons(self, button_region: np.ndarray) -> List[str]:
        """
        Aksiyon butonlarını tespit eder (Fold/Check/Call/Raise/Bet).
        """
        text = self.read_text(button_region).upper()
        actions = []

        if "FOLD" in text:
            actions.append("FOLD")
        if "CHECK" in text:
            actions.append("CHECK")
        if "CALL" in text:
            actions.append("CALL")
        if "BET" in text:
            actions.append("BET")
        if "RAISE" in text:
            actions.append("RAISE")
        if "ALL" in text:
            actions.append("ALL_IN")

        return actions
