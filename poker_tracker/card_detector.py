"""
POKER TRACKER - CARD DETECTOR
==============================
OpenCV ile kart tanıma modülü.
Renk analizi ve şekil eşleştirme ile kartları tespit eder.
"""

import logging
from typing import Optional, List, Tuple, Dict
from dataclasses import dataclass

import numpy as np

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

log = logging.getLogger("CardDetector")

# Kart renk ve rank tanımları
SUIT_COLORS = {
    "h": {"name": "hearts", "color": "red", "symbol": "♥"},
    "d": {"name": "diamonds", "color": "red", "symbol": "♦"},
    "c": {"name": "clubs", "color": "black", "symbol": "♣"},
    "s": {"name": "spades", "color": "black", "symbol": "♠"},
}

RANK_DISPLAY = {
    "2": "2", "3": "3", "4": "4", "5": "5", "6": "6",
    "7": "7", "8": "8", "9": "9", "T": "10",
    "J": "J", "Q": "Q", "K": "K", "A": "A",
}


@dataclass
class DetectedCard:
    """Tespit edilen kart bilgisi."""
    rank: str           # '2'-'9', 'T', 'J', 'Q', 'K', 'A'
    suit: str           # 'c', 'd', 'h', 's'
    confidence: float   # 0-1 arası güven skoru
    region_index: int   # Hangi bölgeden tespit edildi

    def __str__(self) -> str:
        symbol = SUIT_COLORS.get(self.suit, {}).get("symbol", self.suit)
        return f"{RANK_DISPLAY.get(self.rank, self.rank)}{symbol}"

    @property
    def notation(self) -> str:
        """Bot uyumlu format: 'Ah', 'Kc' vb."""
        return f"{self.rank}{self.suit}"


class CardDetector:
    """
    Kart tanıma motoru.

    İki aşamalı tanıma:
    1. Renk analizi ile suit (kupa/karo/maça/sinek) tespiti
    2. Şekil/kontur analizi ile rank (sayı/figür) tespiti
    """

    # HSV renk aralıkları (renk tespiti için)
    RED_LOWER_1 = np.array([0, 70, 50])
    RED_UPPER_1 = np.array([10, 255, 255])
    RED_LOWER_2 = np.array([170, 70, 50])
    RED_UPPER_2 = np.array([180, 255, 255])
    BLACK_LOWER = np.array([0, 0, 0])
    BLACK_UPPER = np.array([180, 255, 80])

    # Rank şablonları - piksel oranlarına dayalı tanıma
    RANK_TEMPLATES: Dict[str, dict] = {}

    def __init__(self, template_dir: Optional[str] = None):
        if not CV2_AVAILABLE:
            raise ImportError("opencv-python gerekli: pip install opencv-python")

        self._template_dir = template_dir
        self._rank_templates: Dict[str, np.ndarray] = {}
        self._suit_templates: Dict[str, np.ndarray] = {}

        if template_dir:
            self._load_templates(template_dir)

    def _load_templates(self, template_dir: str) -> None:
        """Template klasöründen kart şablonlarını yükle."""
        import os

        for rank in ["2", "3", "4", "5", "6", "7", "8", "9", "T", "J", "Q", "K", "A"]:
            path = os.path.join(template_dir, f"rank_{rank}.png")
            if os.path.exists(path):
                tmpl = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if tmpl is not None:
                    self._rank_templates[rank] = tmpl
                    log.debug(f"Rank şablonu yüklendi: {rank}")

        for suit in ["h", "d", "c", "s"]:
            path = os.path.join(template_dir, f"suit_{suit}.png")
            if os.path.exists(path):
                tmpl = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
                if tmpl is not None:
                    self._suit_templates[suit] = tmpl
                    log.debug(f"Suit şablonu yüklendi: {suit}")

    def detect_card(self, card_image: np.ndarray, region_index: int = 0) -> Optional[DetectedCard]:
        """
        Tek bir kart görüntüsünden kartı tanır.

        Args:
            card_image: BGR formatında kart görüntüsü
            region_index: Bölge indeksi

        Returns:
            DetectedCard veya None (kart bulunamazsa)
        """
        if card_image is None or card_image.size == 0:
            return None

        # Kartın var olup olmadığını kontrol et
        if not self._is_card_present(card_image):
            return None

        # Suit tespiti
        suit, suit_conf = self._detect_suit(card_image)
        if suit is None:
            return None

        # Rank tespiti
        rank, rank_conf = self._detect_rank(card_image)
        if rank is None:
            return None

        confidence = (suit_conf + rank_conf) / 2.0

        return DetectedCard(
            rank=rank,
            suit=suit,
            confidence=confidence,
            region_index=region_index
        )

    def detect_multiple_cards(
        self, card_images: List[np.ndarray]
    ) -> List[Optional[DetectedCard]]:
        """Birden fazla kart görüntüsünü tanır."""
        results = []
        for i, img in enumerate(card_images):
            card = self.detect_card(img, region_index=i)
            results.append(card)
        return results

    def _is_card_present(self, image: np.ndarray) -> bool:
        """
        Bölgede kart var mı kontrol eder.
        Boş (yeşil masa) veya siyah alan ise kart yoktur.
        """
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Yeşil masa rengi kontrolü
        green_lower = np.array([35, 40, 40])
        green_upper = np.array([85, 255, 255])
        green_mask = cv2.inRange(hsv, green_lower, green_upper)
        green_ratio = np.sum(green_mask > 0) / green_mask.size

        # Çoğunluk yeşil ise kart yok
        if green_ratio > 0.6:
            return False

        # Beyaz alan kontrolü (kart yüzeyi)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, white_mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        white_ratio = np.sum(white_mask > 0) / white_mask.size

        # Yeterli beyaz alan varsa kart var
        return white_ratio > 0.15

    def _detect_suit(self, image: np.ndarray) -> Tuple[Optional[str], float]:
        """
        Kart rengini (suit) tespit eder.

        Strateji:
        1. Template matching varsa önce onu dene
        2. Yoksa renk analizi kullan
        """
        # Template matching
        if self._suit_templates:
            suit, conf = self._template_match_suit(image)
            if suit and conf > 0.6:
                return suit, conf

        # Renk bazlı tespit
        return self._color_based_suit_detection(image)

    def _color_based_suit_detection(self, image: np.ndarray) -> Tuple[Optional[str], float]:
        """Renk analizi ile suit tespiti."""
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        # Kırmızı piksel sayısı (hearts/diamonds)
        red_mask1 = cv2.inRange(hsv, self.RED_LOWER_1, self.RED_UPPER_1)
        red_mask2 = cv2.inRange(hsv, self.RED_LOWER_2, self.RED_UPPER_2)
        red_mask = cv2.bitwise_or(red_mask1, red_mask2)
        red_count = np.sum(red_mask > 0)

        # Siyah piksel sayısı (clubs/spades)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, black_mask = cv2.threshold(gray, 60, 255, cv2.THRESH_BINARY_INV)
        # Beyaz alanları (kart yüzeyi) çıkar
        _, white_mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        black_only = cv2.bitwise_and(black_mask, cv2.bitwise_not(white_mask))
        black_count = np.sum(black_only > 0)

        total_pixels = image.shape[0] * image.shape[1]
        red_ratio = red_count / total_pixels
        black_ratio = black_count / total_pixels

        is_red = red_ratio > black_ratio and red_ratio > 0.02

        if is_red:
            # Hearts vs Diamonds ayrımı - suit sembolünün şekline bak
            suit_type = self._distinguish_red_suits(image, red_mask)
            return suit_type, 0.7
        elif black_ratio > 0.02:
            # Clubs vs Spades ayrımı
            suit_type = self._distinguish_black_suits(image, black_only)
            return suit_type, 0.7
        else:
            return None, 0.0

    def _distinguish_red_suits(self, image: np.ndarray, red_mask: np.ndarray) -> str:
        """Hearts ve Diamonds arasında ayrım yap."""
        # Suit sembol bölgesini izole et (kartın sol üst köşesi)
        h, w = red_mask.shape
        suit_area = red_mask[int(h * 0.2):int(h * 0.5), 0:int(w * 0.4)]

        if suit_area.size == 0:
            return "h"  # Default hearts

        # Kontur analizi
        contours, _ = cv2.findContours(suit_area, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return "h"

        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)
        perimeter = cv2.arcLength(largest, True)

        if perimeter == 0:
            return "h"

        # Circularity: diamonds daha köşeli (düşük circularity)
        circularity = 4 * np.pi * area / (perimeter * perimeter)

        if circularity < 0.6:
            return "d"  # Diamond (daha köşeli)
        else:
            return "h"  # Heart (daha yuvarlak)

    def _distinguish_black_suits(self, image: np.ndarray, black_mask: np.ndarray) -> str:
        """Clubs ve Spades arasında ayrım yap."""
        h, w = black_mask.shape
        suit_area = black_mask[int(h * 0.2):int(h * 0.5), 0:int(w * 0.4)]

        if suit_area.size == 0:
            return "s"  # Default spades

        contours, _ = cv2.findContours(suit_area, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return "s"

        largest = max(contours, key=cv2.contourArea)
        hull = cv2.convexHull(largest)
        hull_area = cv2.contourArea(hull)
        contour_area = cv2.contourArea(largest)

        if hull_area == 0:
            return "s"

        # Solidity: clubs daha parçalı (düşük solidity)
        solidity = contour_area / hull_area

        if solidity < 0.75:
            return "c"  # Club (3 yapraklı, daha parçalı)
        else:
            return "s"  # Spade (tek yaprak, daha solid)

    def _template_match_suit(self, image: np.ndarray) -> Tuple[Optional[str], float]:
        """Template matching ile suit tespiti."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # Suit bölgesi - sol üst köşe
        h, w = gray.shape
        suit_roi = gray[int(h * 0.25):int(h * 0.50), 0:int(w * 0.35)]

        best_suit = None
        best_conf = 0.0

        for suit, template in self._suit_templates.items():
            # Template'i ROI boyutuna ölçekle
            tmpl_h, tmpl_w = template.shape
            roi_h, roi_w = suit_roi.shape

            if tmpl_h > roi_h or tmpl_w > roi_w:
                scale = min(roi_h / tmpl_h, roi_w / tmpl_w) * 0.8
                template_resized = cv2.resize(
                    template, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA
                )
            else:
                template_resized = template

            if template_resized.shape[0] > suit_roi.shape[0] or template_resized.shape[1] > suit_roi.shape[1]:
                continue

            result = cv2.matchTemplate(suit_roi, template_resized, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)

            if max_val > best_conf:
                best_conf = max_val
                best_suit = suit

        return best_suit, best_conf

    def _detect_rank(self, image: np.ndarray) -> Tuple[Optional[str], float]:
        """
        Kart rank'ini tespit eder.

        Strateji:
        1. Template matching varsa önce onu dene
        2. Yoksa OCR veya kontur analizi kullan
        """
        # Template matching
        if self._rank_templates:
            rank, conf = self._template_match_rank(image)
            if rank and conf > 0.6:
                return rank, conf

        # Kontur bazlı tespit
        return self._contour_based_rank_detection(image)

    def _template_match_rank(self, image: np.ndarray) -> Tuple[Optional[str], float]:
        """Template matching ile rank tespiti."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        # Rank bölgesi - sol üst köşe
        rank_roi = gray[0:int(h * 0.30), 0:int(w * 0.35)]

        best_rank = None
        best_conf = 0.0

        for rank, template in self._rank_templates.items():
            tmpl_h, tmpl_w = template.shape
            roi_h, roi_w = rank_roi.shape

            if tmpl_h > roi_h or tmpl_w > roi_w:
                scale = min(roi_h / tmpl_h, roi_w / tmpl_w) * 0.8
                template_resized = cv2.resize(
                    template, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA
                )
            else:
                template_resized = template

            if template_resized.shape[0] > rank_roi.shape[0] or template_resized.shape[1] > rank_roi.shape[1]:
                continue

            result = cv2.matchTemplate(rank_roi, template_resized, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)

            if max_val > best_conf:
                best_conf = max_val
                best_rank = rank

        return best_rank, best_conf

    def _contour_based_rank_detection(self, image: np.ndarray) -> Tuple[Optional[str], float]:
        """
        Kontur analizi ile rank tespiti.
        Basit bir yaklaşım: rank bölgesindeki kontur sayısı ve oranları.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # Rank bölgesi - sol üst köşe
        rank_roi = gray[0:int(h * 0.30), 0:int(w * 0.40)]

        if rank_roi.size == 0:
            return None, 0.0

        # Threshold
        _, binary = cv2.threshold(rank_roi, 127, 255, cv2.THRESH_BINARY_INV)

        # Konturları bul
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None, 0.0

        # En büyük kontur
        largest = max(contours, key=cv2.contourArea)
        x, y, cw, ch = cv2.boundingRect(largest)
        aspect_ratio = cw / ch if ch > 0 else 0

        # Kontur sayısına ve şekline göre tahmin
        num_contours = len([c for c in contours if cv2.contourArea(c) > 20])

        # Basit heuristik tanıma
        # İki haneli sayılar (10) için özel durum
        if num_contours >= 2 and aspect_ratio > 1.2:
            return "T", 0.5  # 10

        # Figürler genelde daha büyük kontur alanına sahip
        contour_area = cv2.contourArea(largest)
        roi_area = rank_roi.shape[0] * rank_roi.shape[1]
        fill_ratio = contour_area / roi_area if roi_area > 0 else 0

        # Bu noktada kesin tanıma için OCR kullanılmalı
        # Şimdilik None dön, OCR engine devralacak
        return None, 0.0

    def detect_board_cards(self, card_images: List[np.ndarray]) -> List[Optional[DetectedCard]]:
        """Board kartlarını tespit eder (flop/turn/river)."""
        return self.detect_multiple_cards(card_images)

    def detect_hero_cards(self, card_images: List[np.ndarray]) -> List[Optional[DetectedCard]]:
        """Hero'nun elindeki kartları tespit eder."""
        return self.detect_multiple_cards(card_images)
