#!/usr/bin/env python3
"""
POKER TRACKER AGENT - Ana Giriş Noktası
=========================================
Canlı poker oyununu ekrandan takip ederek
overlay ekrana bilgi yazan ajan sistemi.

Kullanım:
    python main.py                    # Varsayılan ayarlarla başlat
    python main.py --console          # Terminal modunda başlat
    python main.py --config config.json  # Özel konfigürasyon dosyası
    python main.py --calibrate        # Ekran bölgesi kalibrasyon modu (manuel)
    python main.py --auto-calibrate   # Otomatik kalibrasyon (ekranı tarar)
    python main.py --auto-calibrate --image screenshot.png  # Görüntüden kalibre et
    python main.py --debug            # Debug modunda başlat

Kısayollar (overlay açıkken):
    ESC     - Programı kapat
    Sürükle - Overlay penceresini taşı
"""

import argparse
import logging
import signal
import sys
import time
import threading
import os
from typing import Optional

# Modül yolunu ayarla
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'poker_bot_v4'))

from config import TrackerConfig, OverlayConfig, ScreenRegion
from game_state_tracker import GameStateTracker
from advisor import StrategyAdvisor, AdvicePackage
from overlay import PokerOverlay, ConsoleOverlay
from auto_calibrator import AutoCalibrator, CalibrationReport

log = logging.getLogger("PokerTracker")


class PokerTrackingAgent:
    """
    Ana poker takip ajanı.

    Döngü:
    1. Ekranı tara (ScreenCapture)
    2. Kartları tanı (CardDetector)
    3. Metin oku (OCREngine)
    4. Durumu güncelle (GameStateTracker)
    5. Strateji analizi yap (StrategyAdvisor)
    6. Overlay'i güncelle (PokerOverlay)
    """

    def __init__(
        self,
        config: Optional[TrackerConfig] = None,
        use_console: bool = False,
        use_mock: bool = False
    ):
        self.config = config or TrackerConfig()

        # Alt sistemler
        self._tracker = GameStateTracker(self.config, use_mock=use_mock)
        self._advisor = StrategyAdvisor()

        if use_console:
            self._overlay = ConsoleOverlay()
        else:
            self._overlay = PokerOverlay(self.config.overlay_config)

        # Kontrol
        self._running = False
        self._scan_thread: Optional[threading.Thread] = None
        self._stats = {
            "scans": 0,
            "hands": 0,
            "errors": 0,
            "start_time": 0,
        }

    def start(self) -> None:
        """Ajanı başlat."""
        log.info("Poker Tracking Agent başlatılıyor...")

        self._running = True
        self._stats["start_time"] = time.time()

        # Overlay'i başlat
        self._overlay.start()
        log.info("Overlay başlatıldı")

        # Tarama döngüsünü ayrı thread'de başlat
        self._scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self._scan_thread.start()
        log.info(f"Tarama döngüsü başlatıldı (aralık: {self.config.scan_interval}s)")

        log.info("Poker Tracking Agent hazır!")

    def _scan_loop(self) -> None:
        """Ana tarama döngüsü."""
        while self._running:
            try:
                cycle_start = time.time()

                # 1. Ekranı tara ve durumu güncelle
                tracked_state = self._tracker.scan()
                self._stats["scans"] += 1

                # 2. GameState'e dönüştür
                game_state = self._tracker.get_game_state()

                # 3. Strateji analizi
                advice = self._advisor.analyze(tracked_state, game_state)
                quick_stats = self._advisor.get_quick_stats(tracked_state)

                # 4. Overlay'i güncelle
                self._overlay.update(advice, quick_stats)

                # 5. Yeni el algılandıysa logla
                if tracked_state.hand_number > self._stats["hands"]:
                    self._stats["hands"] = tracked_state.hand_number
                    self._log_hand_start(tracked_state)

                # Tarama aralığını koru
                elapsed = time.time() - cycle_start
                sleep_time = max(0, self.config.scan_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)

            except KeyboardInterrupt:
                break
            except Exception as e:
                self._stats["errors"] += 1
                log.error(f"Tarama hatası: {e}", exc_info=self.config.debug_mode)
                time.sleep(1)  # Hata durumunda biraz bekle

    def _log_hand_start(self, state) -> None:
        """Yeni el bilgisini loglar."""
        hero_cards = ""
        if state.has_hero_cards:
            hero_cards = " ".join(
                str(c) for c in state.hero_cards if c is not None
            )

        log.info(
            f"El #{state.hand_number} | "
            f"Kartlar: {hero_cards} | "
            f"Pozisyon: {state.hero_position} | "
            f"Stack: ${state.hero_stack:.2f}"
        )

    def stop(self) -> None:
        """Ajanı durdur."""
        log.info("Poker Tracking Agent durduruluyor...")

        self._running = False

        # Overlay kapat
        self._overlay.stop()

        # Tracker kapat
        self._tracker.close()

        # İstatistikler
        elapsed = time.time() - self._stats["start_time"]
        log.info(
            f"Oturum özeti: "
            f"{self._stats['hands']} el, "
            f"{self._stats['scans']} tarama, "
            f"{self._stats['errors']} hata, "
            f"{elapsed:.0f} saniye"
        )

    def get_stats(self) -> dict:
        """Çalışma istatistiklerini döndürür."""
        elapsed = time.time() - self._stats["start_time"] if self._stats["start_time"] > 0 else 0
        return {
            **self._stats,
            "elapsed_seconds": elapsed,
            "scans_per_second": self._stats["scans"] / elapsed if elapsed > 0 else 0,
        }


class AutoCalibrationMode:
    """
    Otomatik ekran kalibrasyon modu.

    Poker masasının ekran görüntüsünü alarak tüm bölgeleri
    otomatik olarak tespit eder. Manuel giriş gerektirmez.
    """

    def run(self, image_path: Optional[str] = None) -> TrackerConfig:
        """
        Otomatik kalibrasyonu çalıştır.

        Args:
            image_path: Opsiyonel. Verilmezse ekran görüntüsü alır.
        """
        print("\n" + "=" * 60)
        print("  POKER TRACKER - Otomatik Kalibrasyon")
        print("=" * 60)
        print()

        calibrator = AutoCalibrator()

        if image_path:
            # Dosyadan kalibre et
            print(f"Görüntü yükleniyor: {image_path}")
            try:
                import cv2
                image = cv2.imread(image_path)
                if image is None:
                    print(f"HATA: Görüntü yüklenemedi: {image_path}")
                    return TrackerConfig()
                print(f"Görüntü boyutu: {image.shape[1]}x{image.shape[0]}")
            except ImportError:
                print("HATA: opencv-python gerekli: pip install opencv-python")
                return TrackerConfig()

            layout, report = calibrator.calibrate_from_image(image)
        else:
            # Ekranı yakala
            print("Poker masanızı açın ve bu ekranda görünür olduğundan emin olun.")
            print()
            input("Hazır olduğunuzda Enter'a basın...")
            print()
            print("Ekran yakalanıyor...")
            print()

            layout, report = calibrator.calibrate()

        # Raporu göster
        print("\n--- Kalibrasyon Raporu ---")
        print(report.summary())

        if not report.success:
            print("\n⚠ Masa tespit edilemedi. Manuel kalibrasyonu deneyin:")
            print("  python poker_tracker/main.py --calibrate")
            return TrackerConfig()

        # Önizleme bilgisi
        if report.preview_path:
            print(f"\nÖnizleme görüntüsü: {report.preview_path}")
            print("Bu dosyayı açarak tespit edilen bölgeleri kontrol edin.")

        # Onay
        print()
        confirm = input("Kalibrasyon sonuçları doğru görünüyor mu? (E/h): ").strip().lower()

        if confirm in ("h", "hayır", "n", "no"):
            print("\nManuel düzeltme moduna geçiliyor...")
            config = self._manual_correction(layout)
        else:
            config = TrackerConfig()
            config.table_layout = layout

        # Blind ve seat bilgisi
        print("\n--- Oyun Ayarları ---")
        config.hero_seat = self._ask_int("Hero koltuk numarası (0-5)", 0, 0, 5)
        config.small_blind = self._ask_float("Small Blind miktarı", 0.5)
        config.big_blind = self._ask_float("Big Blind miktarı", 1.0)

        # Kaydet
        save_path = input("\nKonfigürasyon dosyası yolu (Enter=poker_tracker_config.json): ").strip()
        if not save_path:
            save_path = "poker_tracker_config.json"

        config.save_to_file(save_path)
        print(f"\nKonfigürasyon kaydedildi: {save_path}")
        print(f"Şimdi tracker'ı başlatabilirsiniz:")
        print(f"  python poker_tracker/main.py --config {save_path}")

        return config

    def _manual_correction(self, layout) -> TrackerConfig:
        """Otomatik tespiti manuel düzeltme imkanı."""
        config = TrackerConfig()
        config.table_layout = layout

        print("\nDüzeltmek istediğiniz bölge için yeni koordinat girin.")
        print("Boş bırakırsanız otomatik tespit korunur.")
        print("Format: x y genişlik yükseklik")
        print()

        # Board kartları
        print("--- Board Kartları ---")
        card_names = ["Flop 1", "Flop 2", "Flop 3", "Turn", "River"]
        for i in range(5):
            region = self._ask_region(card_names[i], layout.board_cards[i])
            config.table_layout.board_cards[i] = region

        # Hero kartları
        print("\n--- Hero Kartları ---")
        for i in range(2):
            region = self._ask_region(f"Hero Kart {i + 1}", layout.hero_cards[i])
            config.table_layout.hero_cards[i] = region

        # Pot
        print("\n--- Pot ---")
        config.table_layout.pot_region = self._ask_region("Pot", layout.pot_region)

        return config

    def _ask_region(self, name: str, default: ScreenRegion) -> ScreenRegion:
        default_str = f"{default.x} {default.y} {default.width} {default.height}"
        response = input(f"  {name} [{default_str}]: ").strip()
        if not response:
            return default
        try:
            parts = response.split()
            if len(parts) != 4:
                print("  Geçersiz format, otomatik tespit korunuyor.")
                return default
            return ScreenRegion(int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]))
        except ValueError:
            print("  Geçersiz değer, otomatik tespit korunuyor.")
            return default

    def _ask_int(self, prompt: str, default: int, min_val: int = 0, max_val: int = 100) -> int:
        response = input(f"  {prompt} [varsayılan: {default}]: ").strip()
        if not response:
            return default
        try:
            return max(min_val, min(max_val, int(response)))
        except ValueError:
            return default

    def _ask_float(self, prompt: str, default: float) -> float:
        response = input(f"  {prompt} [varsayılan: {default}]: ").strip()
        if not response:
            return default
        try:
            return float(response)
        except ValueError:
            return default


class CalibrationMode:
    """
    Manuel ekran bölgesi kalibrasyon modu.
    Kullanıcının poker masasının bölgelerini elle ayarlamasına yardımcı olur.
    """

    def __init__(self):
        self._regions = {}

    def run(self) -> TrackerConfig:
        """Kalibrasyon sihirbazını çalıştır."""
        print("\n" + "=" * 60)
        print("  POKER TRACKER - Manuel Kalibrasyon")
        print("=" * 60)
        print()
        print("İPUCU: Otomatik kalibrasyon için --auto-calibrate kullanın!")
        print()
        print("Her bölge için ekran koordinatlarını girin.")
        print("Format: x y genişlik yükseklik")
        print("Örnek: 710 340 70 95")
        print()

        config = TrackerConfig()

        # Hero koltuğu
        hero_seat = self._ask_int("Hero koltuk numarası (0-5)", 0, 0, 5)
        config.hero_seat = hero_seat

        # Blind seviyeleri
        sb = self._ask_float("Small Blind miktarı", 0.5)
        bb = self._ask_float("Big Blind miktarı", 1.0)
        config.small_blind = sb
        config.big_blind = bb

        # Pot bölgesi
        print("\n--- Pot Bölgesi ---")
        pot_region = self._ask_region("Pot", config.table_layout.pot_region)
        config.table_layout.pot_region = pot_region

        # Board kartları
        print("\n--- Board Kart Bölgeleri ---")
        for i in range(5):
            card_names = ["Flop 1", "Flop 2", "Flop 3", "Turn", "River"]
            region = self._ask_region(
                card_names[i],
                config.table_layout.board_cards[i]
            )
            config.table_layout.board_cards[i] = region

        # Hero kartları
        print("\n--- Hero Kart Bölgeleri ---")
        for i in range(2):
            region = self._ask_region(
                f"Hero Kart {i + 1}",
                config.table_layout.hero_cards[i]
            )
            config.table_layout.hero_cards[i] = region

        # Kaydet
        save_path = input("\nKonfigürasyon dosyası yolu (Enter=poker_tracker_config.json): ").strip()
        if not save_path:
            save_path = "poker_tracker_config.json"

        config.save_to_file(save_path)
        print(f"\nKonfigürasyon kaydedildi: {save_path}")

        return config

    def _ask_region(self, name: str, default: ScreenRegion) -> ScreenRegion:
        """Bölge koordinatlarını sor."""
        default_str = f"{default.x} {default.y} {default.width} {default.height}"
        response = input(f"  {name} [varsayılan: {default_str}]: ").strip()

        if not response:
            return default

        try:
            parts = response.split()
            if len(parts) != 4:
                print("  Geçersiz format. Varsayılan kullanılıyor.")
                return default
            return ScreenRegion(int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]))
        except ValueError:
            print("  Geçersiz değer. Varsayılan kullanılıyor.")
            return default

    def _ask_int(self, prompt: str, default: int, min_val: int = 0, max_val: int = 100) -> int:
        """Tam sayı sor."""
        response = input(f"  {prompt} [varsayılan: {default}]: ").strip()
        if not response:
            return default
        try:
            val = int(response)
            return max(min_val, min(max_val, val))
        except ValueError:
            return default

    def _ask_float(self, prompt: str, default: float) -> float:
        """Ondalıklı sayı sor."""
        response = input(f"  {prompt} [varsayılan: {default}]: ").strip()
        if not response:
            return default
        try:
            return float(response)
        except ValueError:
            return default


def setup_logging(debug: bool = False) -> None:
    """Logging konfigürasyonu."""
    level = logging.DEBUG if debug else logging.INFO

    formatter = logging.Formatter(
        "%(asctime)s [%(name)-15s] %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S"
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(handler)

    # Dosya log
    file_handler = logging.FileHandler("poker_tracker.log", encoding="utf-8")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)


def main():
    """Ana giriş noktası."""
    parser = argparse.ArgumentParser(
        description="Poker Tracker Agent - Canlı Poker Overlay Sistemi"
    )
    parser.add_argument(
        "--console", action="store_true",
        help="Terminal modunda çalıştır (GUI yerine)"
    )
    parser.add_argument(
        "--config", type=str, default=None,
        help="Konfigürasyon dosyası yolu"
    )
    parser.add_argument(
        "--calibrate", action="store_true",
        help="Manuel ekran bölgesi kalibrasyon modunu başlat"
    )
    parser.add_argument(
        "--auto-calibrate", action="store_true",
        help="Otomatik kalibrasyon (ekranı tarayarak bölgeleri tespit eder)"
    )
    parser.add_argument(
        "--image", type=str, default=None,
        help="Otomatik kalibrasyon için ekran görüntüsü dosyası"
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Debug modunda çalıştır"
    )
    parser.add_argument(
        "--mock", action="store_true",
        help="Test modu (gerçek ekran yakalama yok)"
    )
    parser.add_argument(
        "--sb", type=float, default=None,
        help="Small Blind miktarı"
    )
    parser.add_argument(
        "--bb", type=float, default=None,
        help="Big Blind miktarı"
    )
    parser.add_argument(
        "--seat", type=int, default=None,
        help="Hero koltuk numarası (0-5)"
    )

    args = parser.parse_args()

    # Logging
    setup_logging(args.debug)

    # Otomatik kalibrasyon
    if args.auto_calibrate:
        auto_cal = AutoCalibrationMode()
        auto_cal.run(image_path=args.image)
        return

    # Manuel kalibrasyon modu
    if args.calibrate:
        calibrator = CalibrationMode()
        calibrator.run()
        return

    # Konfigürasyon yükle
    if args.config:
        config = TrackerConfig.load_from_file(args.config)
    else:
        config = TrackerConfig()

    # Komut satırı override'lar
    if args.sb is not None:
        config.small_blind = args.sb
    if args.bb is not None:
        config.big_blind = args.bb
    if args.seat is not None:
        config.hero_seat = args.seat
    if args.debug:
        config.debug_mode = True

    # Ajanı oluştur
    agent = PokerTrackingAgent(
        config=config,
        use_console=args.console,
        use_mock=args.mock
    )

    # Sinyal yakalama (Ctrl+C)
    def signal_handler(sig, frame):
        log.info("\nKapatma sinyali alındı...")
        agent.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Başlat
    try:
        agent.start()

        # Ana thread'i canlı tut
        print("\nPoker Tracker çalışıyor. Durdurmak için Ctrl+C basın.")
        print("Overlay penceresini sürükleyerek taşıyabilirsiniz.")
        print("ESC tuşu ile kapatabilirsiniz.\n")

        while agent._running:
            time.sleep(1)

    except KeyboardInterrupt:
        pass
    finally:
        agent.stop()


if __name__ == "__main__":
    main()
