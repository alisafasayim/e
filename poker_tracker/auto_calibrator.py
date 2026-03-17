"""
POKER TRACKER - AUTO CALIBRATOR
=================================
Otomatik ekran bölgesi kalibrasyon sistemi.

Poker masasının ekran görüntüsünü analiz ederek:
- Masa sınırını (yeşil keçe)
- Kart yuvalarını (board + hero)
- Pot, bet, stack metin bölgelerini
- Dealer button pozisyonunu
- Aksiyon butonlarını
otomatik olarak tespit eder.

Kullanım:
    calibrator = AutoCalibrator()
    layout = calibrator.calibrate()          # Ekranı yakala + tespit et
    layout = calibrator.calibrate_from_image(img)  # Mevcut görüntüden
"""

import logging
import math
import os
from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass, field

import numpy as np

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

from config import ScreenRegion, TableLayout

log = logging.getLogger("AutoCalibrator")


# ─── Tespit sonucu veri yapıları ───

@dataclass
class DetectionResult:
    """Tek bir tespit sonucu."""
    region: ScreenRegion
    confidence: float = 0.0
    label: str = ""


@dataclass
class CalibrationReport:
    """Kalibrasyon raporu."""
    success: bool = False
    table_found: bool = False
    board_cards_found: int = 0
    hero_cards_found: int = 0
    pot_found: bool = False
    dealer_found: bool = False
    seats_found: int = 0
    action_buttons_found: bool = False
    preview_path: str = ""
    messages: List[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = []
        lines.append(f"  Masa tespiti:      {'✓' if self.table_found else '✗'}")
        lines.append(f"  Board kartları:    {self.board_cards_found}/5")
        lines.append(f"  Hero kartları:     {self.hero_cards_found}/2")
        lines.append(f"  Pot bölgesi:       {'✓' if self.pot_found else '✗'}")
        lines.append(f"  Dealer button:     {'✓' if self.dealer_found else '✗'}")
        lines.append(f"  Oyuncu koltukları: {self.seats_found}/6")
        lines.append(f"  Aksiyon butonları: {'✓' if self.action_buttons_found else '✗'}")
        if self.preview_path:
            lines.append(f"  Önizleme:          {self.preview_path}")
        for msg in self.messages:
            lines.append(f"  ⚠ {msg}")
        return "\n".join(lines)


class AutoCalibrator:
    """
    Otomatik poker masası kalibrasyon sistemi.

    Akış:
    1. Ekran görüntüsü al (veya mevcut görüntüyü kullan)
    2. Yeşil keçe ile masa sınırını tespit et
    3. Beyaz dikdörtgenlerle kart yuvalarını bul
    4. Metin bölgelerini OCR ile tara
    5. Dealer button'ı renk+şekil ile bul
    6. Tüm bölgeleri TableLayout'a dönüştür
    7. Debug önizleme görüntüsü kaydet
    """

    # ─── Yeşil keçe HSV aralığı ───
    GREEN_LOWER = np.array([25, 30, 30])
    GREEN_UPPER = np.array([90, 255, 255])

    # ─── Beyaz kart yüzeyi ───
    WHITE_LOWER = np.array([0, 0, 180])
    WHITE_UPPER = np.array([180, 40, 255])

    # ─── Sarı dealer button ───
    YELLOW_LOWER = np.array([18, 70, 70])
    YELLOW_UPPER = np.array([42, 255, 255])

    # ─── Kart boyut parametreleri ───
    CARD_ASPECT_MIN = 0.55    # width/height min
    CARD_ASPECT_MAX = 0.90    # width/height max
    CARD_MIN_AREA = 800       # Minimum kart alanı (piksel²)
    CARD_MAX_AREA = 30000     # Maksimum kart alanı

    # ─── Aksiyon butonları renk aralıkları ───
    # Fold (kırmızı), Call/Check (yeşil), Raise (turuncu/mavi)
    BUTTON_COLORS = {
        "red":    (np.array([0, 80, 80]),   np.array([10, 255, 255])),
        "green":  (np.array([40, 60, 60]),  np.array([80, 255, 255])),
        "orange": (np.array([10, 80, 80]),  np.array([25, 255, 255])),
        "blue":   (np.array([100, 60, 60]), np.array([130, 255, 255])),
    }

    def __init__(self, screen_capture=None):
        if not CV2_AVAILABLE:
            raise ImportError("opencv-python gerekli: pip install opencv-python")

        self._capture = screen_capture
        self._report = CalibrationReport()

    def calibrate(self, monitor_index: int = 0) -> Tuple[TableLayout, CalibrationReport]:
        """
        Ekranı yakalayıp otomatik kalibre eder.

        Args:
            monitor_index: Hangi monitör (0 = birincil)

        Returns:
            (TableLayout, CalibrationReport)
        """
        # Ekranı yakala
        image = self._capture_screen(monitor_index)
        if image is None:
            self._report.messages.append("Ekran yakalanamadı!")
            return TableLayout(), self._report

        return self.calibrate_from_image(image)

    def calibrate_from_image(self, image: np.ndarray) -> Tuple[TableLayout, CalibrationReport]:
        """
        Mevcut bir görüntüden kalibre eder.

        Args:
            image: BGR formatında ekran görüntüsü

        Returns:
            (TableLayout, CalibrationReport)
        """
        self._report = CalibrationReport()
        layout = TableLayout()

        full_h, full_w = image.shape[:2]
        log.info(f"Görüntü boyutu: {full_w}x{full_h}")

        # ─── Adım 1: Masa sınırını bul ───
        table_bounds, table_mask = self._detect_table_boundary(image)
        if table_bounds is None:
            self._report.messages.append("Poker masası bulunamadı! Yeşil keçe görünmüyor olabilir.")
            # Tüm ekranı masa olarak kabul et
            table_bounds = ScreenRegion(0, 0, full_w, full_h)
        else:
            self._report.table_found = True
            log.info(f"Masa bulundu: ({table_bounds.x}, {table_bounds.y}) {table_bounds.width}x{table_bounds.height}")

        layout.table_window = table_bounds

        # Masa bölgesini kırp
        tx, ty = table_bounds.x, table_bounds.y
        tw, th = table_bounds.width, table_bounds.height
        table_img = image[ty:ty + th, tx:tx + tw]

        # ─── Adım 2: Kart yuvalarını bul ───
        board_cards, hero_cards = self._detect_card_slots(table_img)
        # Koordinatları tam ekrana geri çevir
        board_cards = [self._offset_region(r, tx, ty) for r in board_cards]
        hero_cards = [self._offset_region(r, tx, ty) for r in hero_cards]

        self._report.board_cards_found = len(board_cards)
        self._report.hero_cards_found = len(hero_cards)

        # Board kartlarını 5'e tamamla
        layout.board_cards = self._fill_board_cards(board_cards, table_bounds)
        # Hero kartlarını 2'ye tamamla
        layout.hero_cards = self._fill_hero_cards(hero_cards, table_bounds)

        log.info(f"Board kartları: {len(board_cards)} tespit, 5'e tamamlandı")
        log.info(f"Hero kartları: {len(hero_cards)} tespit, 2'ye tamamlandı")

        # ─── Adım 3: Pot bölgesini bul ───
        pot_region = self._detect_pot_region(table_img, layout.board_cards, tx, ty)
        if pot_region:
            layout.pot_region = pot_region
            self._report.pot_found = True
            log.info(f"Pot bölgesi: ({pot_region.x}, {pot_region.y})")
        else:
            # Varsayılan: board kartlarının hemen üstü
            layout.pot_region = self._estimate_pot_region(layout.board_cards, table_bounds)

        # ─── Adım 4: Dealer button ───
        dealer_regions = self._detect_dealer_button(table_img, tx, ty)
        if dealer_regions:
            self._report.dealer_found = True
            log.info(f"Dealer button bölgeleri: {len(dealer_regions)} tespit")

        # ─── Adım 5: Oyuncu koltukları (bet/stack/isim) ───
        seat_regions = self._detect_player_seats(table_img, table_bounds)
        self._report.seats_found = len(seat_regions)

        if seat_regions:
            self._apply_seat_regions(layout, seat_regions, table_bounds)
        else:
            # Koltuklar otomatik tespit edilemedi → geometrik hesapla
            self._estimate_seat_regions(layout, table_bounds)

        # Dealer button bölgelerini oturma düzenine göre ayarla
        if dealer_regions:
            layout.dealer_button_regions = self._assign_dealer_regions(
                dealer_regions, layout.player_name_regions, table_bounds
            )
        else:
            self._estimate_dealer_regions(layout, table_bounds)

        # ─── Adım 6: Aksiyon butonları ───
        action_region = self._detect_action_buttons(image, table_bounds)
        if action_region:
            layout.action_buttons_region = action_region
            self._report.action_buttons_found = True
            log.info(f"Aksiyon butonları: ({action_region.x}, {action_region.y})")
        else:
            # Varsayılan: masanın altı
            layout.action_buttons_region = ScreenRegion(
                table_bounds.x + table_bounds.width // 4,
                table_bounds.y + int(table_bounds.height * 0.85),
                table_bounds.width // 2,
                60
            )

        # ─── Adım 7: Önizleme oluştur ───
        preview_path = self._save_preview(image, layout)
        self._report.preview_path = preview_path
        self._report.success = self._report.table_found

        return layout, self._report

    # ═══════════════════════════════════════════════════════════════
    # ADIM 1: MASA SINIRI TESPİTİ
    # ═══════════════════════════════════════════════════════════════

    def _detect_table_boundary(self, image: np.ndarray) -> Tuple[Optional[ScreenRegion], Optional[np.ndarray]]:
        """
        Yeşil keçe alanını tespit ederek masa sınırını bulur.

        Returns:
            (ScreenRegion, mask) veya (None, None)
        """
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        green_mask = cv2.inRange(hsv, self.GREEN_LOWER, self.GREEN_UPPER)

        # Morfolojik temizlik (gürültüyü azalt)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, kernel)
        green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_OPEN, kernel)

        # En büyük yeşil konturu bul
        contours, _ = cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None, None

        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)
        img_area = image.shape[0] * image.shape[1]

        # Minimum %5 ekran alanı olmalı
        if area < img_area * 0.05:
            return None, None

        x, y, w, h = cv2.boundingRect(largest)

        # Biraz genişlet (masanın kenarlarındaki oyuncu bilgileri için)
        padding = 30
        x = max(0, x - padding)
        y = max(0, y - padding)
        w = min(image.shape[1] - x, w + 2 * padding)
        h = min(image.shape[0] - y, h + 2 * padding)

        return ScreenRegion(x, y, w, h), green_mask

    # ═══════════════════════════════════════════════════════════════
    # ADIM 2: KART YUVALARI TESPİTİ
    # ═══════════════════════════════════════════════════════════════

    def _detect_card_slots(self, table_image: np.ndarray) -> Tuple[List[ScreenRegion], List[ScreenRegion]]:
        """
        Masa görüntüsünden kart yuvalarını tespit eder.

        Beyaz dikdörtgen bölgeleri arar, kart oranına uyanları seçer,
        Y eksenine göre board (üst) ve hero (alt) olarak gruplar.

        Returns:
            (board_card_regions, hero_card_regions)
        """
        h, w = table_image.shape[:2]
        hsv = cv2.cvtColor(table_image, cv2.COLOR_BGR2HSV)

        # Beyaz alanları bul
        white_mask = cv2.inRange(hsv, self.WHITE_LOWER, self.WHITE_UPPER)

        # Morfolojik temizlik
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        white_mask = cv2.morphologyEx(white_mask, cv2.MORPH_CLOSE, kernel)
        white_mask = cv2.morphologyEx(white_mask, cv2.MORPH_OPEN, kernel)

        # Kontürleri bul
        contours, _ = cv2.findContours(white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        card_candidates = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.CARD_MIN_AREA or area > self.CARD_MAX_AREA:
                continue

            x, y, cw, ch = cv2.boundingRect(cnt)
            aspect = cw / ch if ch > 0 else 0

            if self.CARD_ASPECT_MIN <= aspect <= self.CARD_ASPECT_MAX:
                # Dikdörtgenlik kontrolü (extent)
                rect_area = cw * ch
                extent = area / rect_area if rect_area > 0 else 0
                if extent > 0.6:  # %60+ dikdörtgen
                    card_candidates.append(ScreenRegion(x, y, cw, ch))

        if not card_candidates:
            log.warning("Kart yuvası bulunamadı")
            return [], []

        log.debug(f"{len(card_candidates)} kart adayı bulundu")

        # Y eksenine göre grupla
        center_y = h // 2

        board_candidates = []
        hero_candidates = []

        for card in card_candidates:
            card_center_y = card.y + card.height // 2
            if card_center_y < center_y + h * 0.1:
                board_candidates.append(card)
            else:
                hero_candidates.append(card)

        # X'e göre sırala
        board_candidates.sort(key=lambda r: r.x)
        hero_candidates.sort(key=lambda r: r.x)

        # Board: en fazla 5, ortadaki kümeyi al
        board_cards = self._filter_card_cluster(board_candidates, max_count=5, expected_spacing=True)

        # Hero: en fazla 2, en alttakileri al
        hero_cards = self._filter_card_cluster(hero_candidates, max_count=2, expected_spacing=True)

        return board_cards, hero_cards

    def _filter_card_cluster(
        self, candidates: List[ScreenRegion], max_count: int, expected_spacing: bool
    ) -> List[ScreenRegion]:
        """
        Kart adaylarından tutarlı bir küme seçer.

        Birbirine yakın boyut ve eşit aralıklı olanları tercih eder.
        """
        if len(candidates) <= max_count:
            return candidates

        if not expected_spacing:
            return candidates[:max_count]

        # Boyut tutarlılığı ile filtrele
        if len(candidates) < 2:
            return candidates

        # Medyan boyut
        median_w = sorted([c.width for c in candidates])[len(candidates) // 2]
        median_h = sorted([c.height for c in candidates])[len(candidates) // 2]

        # Medyana yakın olanları seç (±%30 tolerans)
        filtered = [
            c for c in candidates
            if abs(c.width - median_w) < median_w * 0.3
            and abs(c.height - median_h) < median_h * 0.3
        ]

        # Hâlâ çok fazlaysa, en merkezdeki max_count tanesini al
        if len(filtered) > max_count:
            # X ortalamasına en yakın olanları seç
            center_x = sum(c.x for c in filtered) / len(filtered)
            filtered.sort(key=lambda c: abs(c.x + c.width / 2 - center_x))
            filtered = filtered[:max_count]
            filtered.sort(key=lambda r: r.x)

        return filtered

    def _fill_board_cards(self, detected: List[ScreenRegion], table: ScreenRegion) -> List[ScreenRegion]:
        """
        Tespit edilen board kartlarını 5 slota tamamlar.
        Eksik slotları mevcut kartların boyut ve aralığından hesaplar.
        """
        if len(detected) >= 5:
            return detected[:5]

        if len(detected) == 0:
            # Hiç kart bulunamadı → masanın merkezine varsayılan yerleştir
            card_w, card_h = 70, 95
            spacing = 10
            total_w = 5 * card_w + 4 * spacing
            start_x = table.x + (table.width - total_w) // 2
            start_y = table.y + int(table.height * 0.35)
            return [
                ScreenRegion(start_x + i * (card_w + spacing), start_y, card_w, card_h)
                for i in range(5)
            ]

        # Mevcut kartlardan boyut ve aralık hesapla
        avg_w = int(sum(c.width for c in detected) / len(detected))
        avg_h = int(sum(c.height for c in detected) / len(detected))
        avg_y = int(sum(c.y for c in detected) / len(detected))

        if len(detected) >= 2:
            # Aralığı hesapla (x farkları)
            gaps = []
            sorted_cards = sorted(detected, key=lambda r: r.x)
            for i in range(1, len(sorted_cards)):
                gap = sorted_cards[i].x - sorted_cards[i - 1].x
                gaps.append(gap)
            avg_gap = int(sum(gaps) / len(gaps))
        else:
            avg_gap = avg_w + 10

        # İlk kartın x'ini kullanarak 5 slotu hesapla
        first_x = detected[0].x
        # Merkezle
        center_x = table.x + table.width // 2
        total_w = 5 * avg_gap
        start_x = center_x - total_w // 2

        return [
            ScreenRegion(start_x + i * avg_gap, avg_y, avg_w, avg_h)
            for i in range(5)
        ]

    def _fill_hero_cards(self, detected: List[ScreenRegion], table: ScreenRegion) -> List[ScreenRegion]:
        """
        Hero kartlarını 2 slota tamamlar.
        """
        if len(detected) >= 2:
            return detected[:2]

        if len(detected) == 0:
            card_w, card_h = 70, 95
            spacing = 10
            center_x = table.x + table.width // 2
            hero_y = table.y + int(table.height * 0.65)
            return [
                ScreenRegion(center_x - card_w - spacing // 2, hero_y, card_w, card_h),
                ScreenRegion(center_x + spacing // 2, hero_y, card_w, card_h),
            ]

        # 1 kart bulundu → yanına ikincisini ekle
        card = detected[0]
        gap = card.width + 10
        second = ScreenRegion(card.x + gap, card.y, card.width, card.height)
        return [card, second]

    # ═══════════════════════════════════════════════════════════════
    # ADIM 3: POT BÖLGESİ TESPİTİ
    # ═══════════════════════════════════════════════════════════════

    def _detect_pot_region(
        self, table_image: np.ndarray,
        board_cards: List[ScreenRegion],
        offset_x: int, offset_y: int
    ) -> Optional[ScreenRegion]:
        """
        Pot metin bölgesini tespit eder.
        Board kartlarının hemen üstünde sayısal metin arar.
        """
        h, w = table_image.shape[:2]

        if not board_cards:
            # Board kartları yoksa masanın merkezinde ara
            search_y = int(h * 0.2)
            search_h = int(h * 0.2)
            search_x = int(w * 0.3)
            search_w = int(w * 0.4)
        else:
            # Board kartlarının üst kısmı (global koordinatlardan lokal'e çevir)
            min_y = min(c.y for c in board_cards) - offset_y
            mid_x = sum(c.x for c in board_cards) / len(board_cards) - offset_x
            search_y = max(0, min_y - 80)
            search_h = 60
            search_x = max(0, int(mid_x - 120))
            search_w = 240

        # Sınır kontrolü
        search_x = max(0, min(search_x, w - 10))
        search_y = max(0, min(search_y, h - 10))
        search_w = min(search_w, w - search_x)
        search_h = min(search_h, h - search_y)

        roi = table_image[search_y:search_y + search_h, search_x:search_x + search_w]
        if roi.size == 0:
            return None

        # Metin bölgeleri bul (MSER veya threshold + kontur)
        text_regions = self._find_text_regions(roi)

        if text_regions:
            # En merkezdeki metin bölgesini seç
            best = text_regions[0]
            return ScreenRegion(
                offset_x + search_x + best.x,
                offset_y + search_y + best.y,
                max(best.width, 200),
                max(best.height, 40)
            )

        # Bulunamazsa tahmini bölge döndür
        return ScreenRegion(
            offset_x + search_x,
            offset_y + search_y,
            search_w,
            search_h
        )

    def _estimate_pot_region(self, board_cards: List[ScreenRegion], table: ScreenRegion) -> ScreenRegion:
        """Board kartlarının üstüne pot bölgesi tahmin eder."""
        if board_cards:
            min_y = min(c.y for c in board_cards)
            center_x = sum(c.x + c.width // 2 for c in board_cards) // len(board_cards)
            return ScreenRegion(center_x - 100, min_y - 50, 200, 40)
        else:
            return ScreenRegion(
                table.x + table.width // 2 - 100,
                table.y + int(table.height * 0.25),
                200, 40
            )

    # ═══════════════════════════════════════════════════════════════
    # ADIM 4: DEALER BUTTON TESPİTİ
    # ═══════════════════════════════════════════════════════════════

    def _detect_dealer_button(
        self, table_image: np.ndarray,
        offset_x: int, offset_y: int
    ) -> List[ScreenRegion]:
        """
        Dealer button'ı tespit eder (sarı/beyaz daire).

        HoughCircles + renk filtresi kombinasyonu.
        """
        hsv = cv2.cvtColor(table_image, cv2.COLOR_BGR2HSV)
        yellow_mask = cv2.inRange(hsv, self.YELLOW_LOWER, self.YELLOW_UPPER)

        # Beyaz de olabilir (bazı istemcilerde)
        white_lower = np.array([0, 0, 200])
        white_upper = np.array([180, 30, 255])
        white_mask = cv2.inRange(hsv, white_lower, white_upper)

        combined = cv2.bitwise_or(yellow_mask, white_mask)

        # Morfolojik temizlik
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)

        # Daire tespiti
        gray = cv2.cvtColor(table_image, cv2.COLOR_BGR2GRAY)
        gray_blurred = cv2.GaussianBlur(gray, (9, 9), 2)

        circles = cv2.HoughCircles(
            gray_blurred,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=50,
            param1=100,
            param2=30,
            minRadius=8,
            maxRadius=25
        )

        results = []

        if circles is not None:
            circles = np.uint16(np.around(circles))
            for circle in circles[0]:
                cx, cy, r = int(circle[0]), int(circle[1]), int(circle[2])

                # Bu dairenin sarı/beyaz maskındaki oranını kontrol et
                mask_roi = combined[
                    max(0, cy - r):min(combined.shape[0], cy + r),
                    max(0, cx - r):min(combined.shape[1], cx + r)
                ]
                if mask_roi.size == 0:
                    continue

                color_ratio = np.sum(mask_roi > 0) / mask_roi.size
                if color_ratio > 0.15:
                    btn_size = r * 2 + 6
                    results.append(ScreenRegion(
                        offset_x + cx - r - 3,
                        offset_y + cy - r - 3,
                        btn_size, btn_size
                    ))

        # HoughCircles bulamazsa, kontur bazlı fallback
        if not results:
            contours, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if 200 < area < 3000:
                    perimeter = cv2.arcLength(cnt, True)
                    if perimeter == 0:
                        continue
                    circularity = 4 * math.pi * area / (perimeter * perimeter)
                    if circularity > 0.6:  # Yuvarlağa yakın
                        x, y, cw, ch = cv2.boundingRect(cnt)
                        results.append(ScreenRegion(
                            offset_x + x, offset_y + y, cw, ch
                        ))

        return results

    # ═══════════════════════════════════════════════════════════════
    # ADIM 5: OYUNCU KOLTUKLARI
    # ═══════════════════════════════════════════════════════════════

    def _detect_player_seats(
        self, table_image: np.ndarray, table_bounds: ScreenRegion
    ) -> List[Dict[str, ScreenRegion]]:
        """
        Masa çevresindeki oyuncu koltuk bölgelerini tespit eder.

        MSER + kontur analizi ile metin bölgelerini bulur,
        eliptik düzende 6 koltuğa atar.
        """
        h, w = table_image.shape[:2]

        # Metin bölgelerini bul
        text_regions = self._find_text_regions(table_image)

        if len(text_regions) < 3:
            return []

        # Metin bölgelerini masa çevresine göre 6 sektöre grupla
        center_x, center_y = w // 2, h // 2
        sectors = self._assign_to_sectors(text_regions, center_x, center_y, num_sectors=6)

        seats = []
        for sector_regions in sectors:
            if not sector_regions:
                continue

            # Her sektörde en büyük metin bölgesini "isim" olarak al
            sector_regions.sort(key=lambda r: r.width * r.height, reverse=True)
            name_region = sector_regions[0]

            seat = {
                "name": ScreenRegion(
                    table_bounds.x + name_region.x,
                    table_bounds.y + name_region.y,
                    max(name_region.width, 160),
                    max(name_region.height, 25)
                ),
            }

            # Stack bölgesi: ismin hemen altı
            seat["stack"] = ScreenRegion(
                seat["name"].x,
                seat["name"].y + seat["name"].height + 2,
                seat["name"].width,
                25
            )

            # Bet bölgesi: isim ile merkez arasında
            bet_x = seat["name"].x + (center_x + table_bounds.x - seat["name"].x) // 3
            bet_y = seat["name"].y + (center_y + table_bounds.y - seat["name"].y) // 3
            seat["bet"] = ScreenRegion(bet_x, bet_y, 120, 30)

            seats.append(seat)

        return seats

    def _assign_to_sectors(
        self, regions: List[ScreenRegion],
        center_x: int, center_y: int,
        num_sectors: int = 6
    ) -> List[List[ScreenRegion]]:
        """
        Bölgeleri açısal sektörlere atar.
        6-max masa: 0=alt(hero), 1=sağ-alt, 2=sağ-üst, 3=üst, 4=sol-üst, 5=sol-alt
        """
        sectors = [[] for _ in range(num_sectors)]
        sector_angle = 360 / num_sectors

        for region in regions:
            rx = region.x + region.width // 2 - center_x
            ry = center_y - (region.y + region.height // 2)  # Y ters

            angle = math.degrees(math.atan2(ry, rx))
            # 0° sağ, 90° üst → 270° alt (hero) olacak şekilde döndür
            angle = (angle + 90) % 360  # 0° = üst, 270° = alt olsun
            # Aslında: 0=üst, 60=sağ-üst, ... → hero = alt = 180°
            # Düzeltme: hero'yu alta koy
            angle = (angle + 180) % 360  # 0° = alt (hero)

            sector_idx = int(angle / sector_angle) % num_sectors
            sectors[sector_idx].append(region)

        return sectors

    def _apply_seat_regions(
        self, layout: TableLayout,
        seats: List[Dict[str, ScreenRegion]],
        table_bounds: ScreenRegion
    ) -> None:
        """Tespit edilen koltuk bölgelerini layout'a uygular."""
        for i, seat in enumerate(seats[:6]):
            if "name" in seat:
                layout.player_name_regions[i] = seat["name"]
            if "stack" in seat:
                layout.stack_regions[i] = seat["stack"]
            if "bet" in seat:
                layout.bet_regions[i] = seat["bet"]

    def _estimate_seat_regions(self, layout: TableLayout, table: ScreenRegion) -> None:
        """
        Koltuklar tespit edilemediğinde geometrik olarak hesaplar.
        6-max masa eliptik düzeni:

            [3]      [4]
        [2]              [5]
            [1]      [0/Hero]
        """
        cx = table.x + table.width // 2
        cy = table.y + table.height // 2
        rx = int(table.width * 0.40)   # Elips X yarıçapı
        ry = int(table.height * 0.38)  # Elips Y yarıçapı

        # Koltuk açıları (derece) - 0=hero(alt), saat yönünde
        angles = [270, 330, 30, 90, 150, 210]

        for i, angle_deg in enumerate(angles):
            rad = math.radians(angle_deg)
            seat_x = int(cx + rx * math.cos(rad))
            seat_y = int(cy - ry * math.sin(rad))

            # İsim bölgesi
            layout.player_name_regions[i] = ScreenRegion(
                seat_x - 80, seat_y - 12, 160, 25
            )

            # Stack bölgesi (ismin altı)
            layout.stack_regions[i] = ScreenRegion(
                seat_x - 80, seat_y + 15, 160, 25
            )

            # Bet bölgesi (koltuk ile merkez arasında)
            bet_x = seat_x + (cx - seat_x) // 3
            bet_y = seat_y + (cy - seat_y) // 3
            layout.bet_regions[i] = ScreenRegion(
                bet_x - 60, bet_y - 15, 120, 30
            )

    def _estimate_dealer_regions(self, layout: TableLayout, table: ScreenRegion) -> None:
        """Dealer button bölgelerini koltuk pozisyonlarından tahmin eder."""
        for i in range(6):
            name = layout.player_name_regions[i]
            cx = table.x + table.width // 2
            cy = table.y + table.height // 2

            # Button, koltuk ile merkez arasında
            bx = name.x + (cx - name.x) // 4
            by = name.y + (cy - name.y) // 4

            layout.dealer_button_regions[i] = ScreenRegion(bx, by, 30, 30)

    def _assign_dealer_regions(
        self, detected: List[ScreenRegion],
        seat_names: List[ScreenRegion],
        table: ScreenRegion
    ) -> List[ScreenRegion]:
        """Tespit edilen dealer button'ları en yakın koltuğa atar."""
        result = []
        for i in range(6):
            seat_center = (
                seat_names[i].x + seat_names[i].width // 2,
                seat_names[i].y + seat_names[i].height // 2
            )

            # En yakın button'ı bul
            best = None
            best_dist = float('inf')
            for btn in detected:
                btn_center = (btn.x + btn.width // 2, btn.y + btn.height // 2)
                dist = math.hypot(
                    btn_center[0] - seat_center[0],
                    btn_center[1] - seat_center[1]
                )
                if dist < best_dist:
                    best_dist = dist
                    best = btn

            if best and best_dist < table.width * 0.2:
                result.append(ScreenRegion(best.x, best.y, best.width, best.height))
            else:
                # Tahmin
                cx = table.x + table.width // 2
                cy = table.y + table.height // 2
                bx = seat_center[0] + (cx - seat_center[0]) // 4
                by = seat_center[1] + (cy - seat_center[1]) // 4
                result.append(ScreenRegion(bx, by, 30, 30))

        return result

    # ═══════════════════════════════════════════════════════════════
    # ADIM 6: AKSİYON BUTONLARI
    # ═══════════════════════════════════════════════════════════════

    def _detect_action_buttons(
        self, full_image: np.ndarray, table_bounds: ScreenRegion
    ) -> Optional[ScreenRegion]:
        """
        Aksiyon butonlarını (Fold/Check/Call/Raise) tespit eder.
        Masanın alt kısmında renkli dikdörtgen butonlar arar.
        """
        h, w = full_image.shape[:2]

        # Alt %25 alanda ara
        search_y = table_bounds.y + int(table_bounds.height * 0.70)
        search_h = min(h - search_y, int(table_bounds.height * 0.30))
        if search_h <= 0:
            return None

        roi = full_image[search_y:search_y + search_h, table_bounds.x:table_bounds.x + table_bounds.width]
        if roi.size == 0:
            return None

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

        # Tüm buton renklerini birleştir
        total_mask = np.zeros(roi.shape[:2], dtype=np.uint8)
        for color_name, (lower, upper) in self.BUTTON_COLORS.items():
            mask = cv2.inRange(hsv, lower, upper)
            total_mask = cv2.bitwise_or(total_mask, mask)

        # İkinci kırmızı aralık
        red2_mask = cv2.inRange(hsv, np.array([170, 80, 80]), np.array([180, 255, 255]))
        total_mask = cv2.bitwise_or(total_mask, red2_mask)

        # Morfolojik temizlik
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 5))
        total_mask = cv2.morphologyEx(total_mask, cv2.MORPH_CLOSE, kernel)

        # En büyük renkli alanı bul
        contours, _ = cv2.findContours(total_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        # Yatay şerit (buton grubu) ara
        button_contours = []
        for cnt in contours:
            x, y, cw, ch = cv2.boundingRect(cnt)
            area = cv2.contourArea(cnt)
            if area > 500 and cw > ch:  # Buton: yatay dikdörtgen
                button_contours.append((x, y, cw, ch))

        if not button_contours:
            return None

        # Tüm butonları kapsayan bölge
        min_x = min(b[0] for b in button_contours)
        min_y = min(b[1] for b in button_contours)
        max_x = max(b[0] + b[2] for b in button_contours)
        max_y = max(b[1] + b[3] for b in button_contours)

        return ScreenRegion(
            table_bounds.x + min_x,
            search_y + min_y,
            max_x - min_x,
            max_y - min_y
        )

    # ═══════════════════════════════════════════════════════════════
    # YARDIMCI METODLAR
    # ═══════════════════════════════════════════════════════════════

    def _find_text_regions(self, image: np.ndarray) -> List[ScreenRegion]:
        """
        Görüntüdeki metin bölgelerini tespit eder.
        MSER (Maximally Stable Extremal Regions) algoritması kullanır.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image

        # MSER ile metin bölgeleri tespiti
        mser = cv2.MSER_create()
        mser.setMinArea(60)
        mser.setMaxArea(5000)

        regions, _ = mser.detectRegions(gray)

        if not regions:
            return []

        # Bounding box'ları hesapla
        bboxes = []
        for region in regions:
            x, y, w, h = cv2.boundingRect(region.reshape(-1, 1, 2))
            aspect = w / h if h > 0 else 0
            # Metin genellikle yatay ve küçüktür
            if 0.1 < aspect < 15 and 5 < h < 60 and w > 8:
                bboxes.append(ScreenRegion(x, y, w, h))

        # Yakın bölgeleri birleştir
        merged = self._merge_nearby_regions(bboxes, x_threshold=15, y_threshold=8)

        return merged

    def _merge_nearby_regions(
        self, regions: List[ScreenRegion],
        x_threshold: int = 15, y_threshold: int = 8
    ) -> List[ScreenRegion]:
        """Yakın bölgeleri birleştirir."""
        if not regions:
            return []

        # Y'ye göre sırala
        sorted_regions = sorted(regions, key=lambda r: (r.y, r.x))

        merged = []
        current = sorted_regions[0]

        for r in sorted_regions[1:]:
            # Mevcut ile yakın mı?
            if (abs(r.y - current.y) < y_threshold and
                    r.x < current.x + current.width + x_threshold):
                # Birleştir
                new_x = min(current.x, r.x)
                new_y = min(current.y, r.y)
                new_right = max(current.x + current.width, r.x + r.width)
                new_bottom = max(current.y + current.height, r.y + r.height)
                current = ScreenRegion(new_x, new_y, new_right - new_x, new_bottom - new_y)
            else:
                merged.append(current)
                current = r

        merged.append(current)

        # Çok küçük bölgeleri filtrele
        merged = [r for r in merged if r.width > 20 and r.height > 8]

        return merged

    def _offset_region(self, region: ScreenRegion, dx: int, dy: int) -> ScreenRegion:
        """Bölge koordinatlarını offset kadar kaydırır."""
        return ScreenRegion(region.x + dx, region.y + dy, region.width, region.height)

    def _capture_screen(self, monitor_index: int = 0) -> Optional[np.ndarray]:
        """Tam ekranı yakalar."""
        if self._capture:
            try:
                from config import ScreenRegion
                # Tam ekran
                import mss
                sct = mss.mss()
                monitors = sct.monitors
                if monitor_index + 1 < len(monitors):
                    mon = monitors[monitor_index + 1]  # 0 = tüm ekranlar
                else:
                    mon = monitors[0]
                region = ScreenRegion(mon["left"], mon["top"], mon["width"], mon["height"])
                return self._capture.capture_region(region)
            except Exception as e:
                log.error(f"Ekran yakalama hatası: {e}")

        # Doğrudan mss kullan
        try:
            import mss
            sct = mss.mss()
            monitors = sct.monitors
            if monitor_index + 1 < len(monitors):
                mon = monitors[monitor_index + 1]
            else:
                mon = monitors[0]

            screenshot = sct.grab(mon)
            img = np.array(screenshot)
            img = img[:, :, :3]  # BGRA → BGR
            sct.close()
            return img
        except Exception as e:
            log.error(f"mss ekran yakalama hatası: {e}")
            return None

    # ═══════════════════════════════════════════════════════════════
    # ÖNİZLEME
    # ═══════════════════════════════════════════════════════════════

    def _save_preview(
        self, image: np.ndarray, layout: TableLayout,
        filepath: str = "calibration_preview.png"
    ) -> str:
        """
        Tespit edilen bölgeleri görüntü üzerine çizerek kaydeder.

        Renk kodları:
        - Yeşil:  Masa sınırı
        - Mavi:   Board kartları
        - Cyan:   Hero kartları
        - Sarı:   Pot bölgesi
        - Turuncu: Bet bölgeleri
        - Pembe:  Oyuncu isimleri
        - Beyaz:  Stack bölgeleri
        - Kırmızı: Dealer button
        - Mor:    Aksiyon butonları
        """
        preview = image.copy()

        # Renk tanımları (BGR)
        COLORS = {
            "table":   (0, 255, 0),     # Yeşil
            "board":   (255, 100, 0),    # Mavi
            "hero":    (255, 255, 0),    # Cyan
            "pot":     (0, 255, 255),    # Sarı
            "bet":     (0, 165, 255),    # Turuncu
            "name":    (180, 105, 255),  # Pembe
            "stack":   (255, 255, 255),  # Beyaz
            "dealer":  (0, 0, 255),      # Kırmızı
            "action":  (255, 0, 255),    # Mor
        }
        THICKNESS = 2

        def draw_region(region: ScreenRegion, color, label: str = ""):
            pt1 = (region.x, region.y)
            pt2 = (region.x + region.width, region.y + region.height)
            cv2.rectangle(preview, pt1, pt2, color, THICKNESS)
            if label:
                cv2.putText(
                    preview, label,
                    (region.x, region.y - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1
                )

        # Masa sınırı
        draw_region(layout.table_window, COLORS["table"], "TABLE")

        # Board kartları
        for i, card in enumerate(layout.board_cards):
            labels = ["F1", "F2", "F3", "T", "R"]
            draw_region(card, COLORS["board"], labels[i] if i < len(labels) else f"B{i}")

        # Hero kartları
        for i, card in enumerate(layout.hero_cards):
            draw_region(card, COLORS["hero"], f"H{i + 1}")

        # Pot
        draw_region(layout.pot_region, COLORS["pot"], "POT")

        # Bet bölgeleri
        for i, bet in enumerate(layout.bet_regions):
            draw_region(bet, COLORS["bet"], f"BET{i}")

        # Oyuncu isimleri
        for i, name in enumerate(layout.player_name_regions):
            draw_region(name, COLORS["name"], f"P{i}")

        # Stack bölgeleri
        for i, stack in enumerate(layout.stack_regions):
            draw_region(stack, COLORS["stack"], f"S{i}")

        # Dealer button
        for i, dealer in enumerate(layout.dealer_button_regions):
            draw_region(dealer, COLORS["dealer"], f"D{i}")

        # Aksiyon butonları
        draw_region(layout.action_buttons_region, COLORS["action"], "ACTIONS")

        # Lejant çiz
        legend_y = 30
        for label, color in COLORS.items():
            cv2.putText(
                preview, label.upper(),
                (15, legend_y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1
            )
            legend_y += 22

        # Kaydet
        cv2.imwrite(filepath, preview)
        log.info(f"Önizleme kaydedildi: {filepath}")

        return filepath
