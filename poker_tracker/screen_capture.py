"""
POKER TRACKER - SCREEN CAPTURE
===============================
Ekran görüntüsü yakalama modülü.
mss kütüphanesi ile hızlı ekran yakalama.
"""

import logging
import time
from typing import Optional

import numpy as np

try:
    import mss
    import mss.tools
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from config import ScreenRegion

log = logging.getLogger("ScreenCapture")


class ScreenCapture:
    """Ekran yakalama sınıfı."""

    def __init__(self):
        if not MSS_AVAILABLE:
            raise ImportError(
                "mss kütüphanesi gerekli: pip install mss"
            )
        self._sct = mss.mss()
        self._last_capture_time: float = 0
        self._frame_count: int = 0

    def capture_region(self, region: ScreenRegion) -> np.ndarray:
        """
        Belirtilen ekran bölgesini yakalar.

        Returns:
            numpy array (BGR formatı, OpenCV uyumlu)
        """
        monitor = region.as_dict
        screenshot = self._sct.grab(monitor)

        # BGRA -> BGR (OpenCV formatı)
        img = np.array(screenshot)
        img = img[:, :, :3]  # Alpha kanalını kaldır

        self._last_capture_time = time.time()
        self._frame_count += 1

        return img

    def capture_full_table(self, table_region: ScreenRegion) -> np.ndarray:
        """Tüm masa alanını yakalar."""
        return self.capture_region(table_region)

    def capture_multiple_regions(self, regions: list) -> list:
        """Birden fazla bölgeyi yakalar."""
        results = []
        for region in regions:
            img = self.capture_region(region)
            results.append(img)
        return results

    def save_screenshot(self, img: np.ndarray, filepath: str) -> None:
        """Screenshot'ı dosyaya kaydet (debug için)."""
        try:
            import cv2
            cv2.imwrite(filepath, img)
            log.debug(f"Screenshot kaydedildi: {filepath}")
        except ImportError:
            if PIL_AVAILABLE:
                # BGR -> RGB
                rgb_img = img[:, :, ::-1]
                pil_img = Image.fromarray(rgb_img)
                pil_img.save(filepath)
                log.debug(f"Screenshot kaydedildi (PIL): {filepath}")

    @property
    def fps(self) -> float:
        """Yaklaşık FPS."""
        if self._last_capture_time == 0:
            return 0.0
        elapsed = time.time() - self._last_capture_time
        if elapsed == 0:
            return 0.0
        return 1.0 / elapsed

    def close(self):
        """Kaynakları serbest bırak."""
        if hasattr(self, '_sct'):
            self._sct.close()

    def __del__(self):
        self.close()


class MockScreenCapture:
    """
    Test ve geliştirme için sahte ekran yakalama.
    Gerçek ekran erişimi olmadan çalışır.
    """

    def __init__(self, test_image_path: Optional[str] = None):
        self._test_image = None
        if test_image_path:
            try:
                import cv2
                self._test_image = cv2.imread(test_image_path)
            except ImportError:
                pass

    def capture_region(self, region: ScreenRegion) -> np.ndarray:
        """Sahte bölge yakalama - boş veya test görüntüsü döner."""
        if self._test_image is not None:
            x, y = region.x, region.y
            w, h = region.width, region.height
            h_img, w_img = self._test_image.shape[:2]
            # Sınır kontrolü
            x2 = min(x + w, w_img)
            y2 = min(y + h, h_img)
            x = max(0, x)
            y = max(0, y)
            return self._test_image[y:y2, x:x2].copy()

        # Boş siyah görüntü
        return np.zeros((region.height, region.width, 3), dtype=np.uint8)

    def capture_full_table(self, table_region: ScreenRegion) -> np.ndarray:
        return self.capture_region(table_region)

    def capture_multiple_regions(self, regions: list) -> list:
        return [self.capture_region(r) for r in regions]

    def save_screenshot(self, img: np.ndarray, filepath: str) -> None:
        pass

    def close(self):
        pass
