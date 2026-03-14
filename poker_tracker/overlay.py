"""
POKER TRACKER - OVERLAY DISPLAY
=================================
Transparent tkinter overlay penceresi.
Oyun bilgilerini ekranın üzerine yazar.
"""

import logging
import threading
import time
from typing import Optional, Dict, List

try:
    import tkinter as tk
    from tkinter import font as tkfont
    TK_AVAILABLE = True
except ImportError:
    TK_AVAILABLE = False

from config import OverlayConfig
from advisor import AdvicePackage, StreetAdvice

log = logging.getLogger("Overlay")

# Suit sembolleri ve renkleri
SUIT_SYMBOLS = {"h": "♥", "d": "♦", "c": "♣", "s": "♠"}
SUIT_COLORS = {"h": "#ff4444", "d": "#ff4444", "c": "#ffffff", "s": "#ffffff"}
RANK_DISPLAY = {
    "2": "2", "3": "3", "4": "4", "5": "5", "6": "6",
    "7": "7", "8": "8", "9": "9", "T": "10",
    "J": "J", "Q": "Q", "K": "K", "A": "A"
}


class PokerOverlay:
    """
    Poker overlay penceresi.
    Masanın üzerinde yarı-saydam bilgi paneli gösterir.
    """

    def __init__(self, config: Optional[OverlayConfig] = None):
        if not TK_AVAILABLE:
            raise ImportError("tkinter gerekli (Python ile birlikte gelir)")

        self.config = config or OverlayConfig()
        self._root: Optional[tk.Tk] = None
        self._canvas: Optional[tk.Canvas] = None
        self._running = False
        self._lock = threading.Lock()

        # Widget referansları
        self._widgets: Dict[str, int] = {}  # canvas item id'leri

    def start(self) -> None:
        """Overlay penceresini başlat (ayrı thread'de)."""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_tk, daemon=True)
        self._thread.start()

        # TK başlayana kadar bekle
        timeout = 5.0
        start = time.time()
        while self._root is None and time.time() - start < timeout:
            time.sleep(0.05)

    def _run_tk(self) -> None:
        """Tkinter event loop (ayrı thread)."""
        self._root = tk.Tk()
        self._root.title("Poker Tracker")

        # Şeffaf, her zaman üstte, çerçevesiz pencere
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)

        # Platform bazlı şeffaflık
        try:
            self._root.attributes("-alpha", self.config.opacity)
        except tk.TclError:
            pass

        # Linux'ta compositing desteği
        try:
            self._root.wait_visibility(self._root)
            self._root.wm_attributes("-type", "dock")
        except (tk.TclError, AttributeError):
            pass

        # Pozisyon ve boyut
        self._root.geometry(
            f"{self.config.width}x{self.config.height}"
            f"+{self.config.x}+{self.config.y}"
        )

        # Canvas
        self._canvas = tk.Canvas(
            self._root,
            width=self.config.width,
            height=self.config.height,
            bg=self.config.bg_color,
            highlightthickness=0
        )
        self._canvas.pack(fill=tk.BOTH, expand=True)

        # Sürükleme desteği
        self._drag_data = {"x": 0, "y": 0}
        self._canvas.bind("<Button-1>", self._on_drag_start)
        self._canvas.bind("<B1-Motion>", self._on_drag_motion)

        # ESC ile kapat
        self._root.bind("<Escape>", lambda e: self.stop())

        # İlk çizim
        self._draw_initial()

        try:
            self._root.mainloop()
        except Exception:
            pass

    def _on_drag_start(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _on_drag_motion(self, event):
        dx = event.x - self._drag_data["x"]
        dy = event.y - self._drag_data["y"]
        x = self._root.winfo_x() + dx
        y = self._root.winfo_y() + dy
        self._root.geometry(f"+{x}+{y}")

    def _draw_initial(self) -> None:
        """İlk boş ekranı çizer."""
        c = self._canvas
        cfg = self.config

        # Başlık
        self._widgets["title"] = c.create_text(
            cfg.width // 2, 20,
            text="POKER TRACKER",
            fill=cfg.accent_color,
            font=(cfg.font_family, cfg.title_font_size, "bold"),
            anchor="center"
        )

        # Ayırıcı çizgi
        c.create_line(
            10, 40, cfg.width - 10, 40,
            fill=cfg.accent_color, width=1
        )

        # Bekleme mesajı
        self._widgets["waiting"] = c.create_text(
            cfg.width // 2, cfg.height // 2,
            text="Masa bekleniyor...",
            fill=cfg.text_color,
            font=(cfg.font_family, cfg.font_size),
            anchor="center"
        )

    def update(self, advice: AdvicePackage, quick_stats: Dict[str, str]) -> None:
        """
        Overlay'i yeni bilgilerle günceller.
        Thread-safe.
        """
        if not self._running or self._root is None:
            return

        with self._lock:
            try:
                self._root.after(0, self._do_update, advice, quick_stats)
            except Exception as e:
                log.error(f"Overlay güncelleme hatası: {e}")

    def _do_update(self, advice: AdvicePackage, quick_stats: Dict[str, str]) -> None:
        """Ana thread'de overlay güncelleme."""
        c = self._canvas
        cfg = self.config

        if c is None:
            return

        # Eski widget'ları temizle (başlık hariç)
        for tag in ["stats", "cards", "advice", "board", "info", "draw"]:
            c.delete(tag)

        # Bekleme mesajını kaldır
        if "waiting" in self._widgets:
            c.delete(self._widgets["waiting"])
            del self._widgets["waiting"]

        y = 55  # Başlık altından başla

        # ─── QUICK STATS ───
        y = self._draw_quick_stats(c, cfg, y, quick_stats)

        # ─── ANA ÖNERİ ───
        y = self._draw_primary_advice(c, cfg, y, advice)

        # ─── EL BİLGİSİ ───
        y = self._draw_hand_info(c, cfg, y, advice)

        # ─── BOARD BİLGİSİ ───
        y = self._draw_board_info(c, cfg, y, advice)

        # ─── DRAW BİLGİSİ ───
        if advice.has_draw:
            y = self._draw_draw_info(c, cfg, y, advice)

        # ─── REASONING ───
        if advice.primary_advice and advice.primary_advice.reasoning:
            y = self._draw_reasoning(c, cfg, y, advice)

    def _draw_quick_stats(self, c, cfg, y, stats: Dict[str, str]) -> int:
        """Hızlı istatistikleri çizer."""
        x = 15
        col_width = (cfg.width - 30) // min(len(stats), 3)

        for i, (key, value) in enumerate(stats.items()):
            col = i % 3
            row = i // 3
            cx = x + col * col_width
            cy = y + row * 30

            # Etiket
            c.create_text(
                cx, cy,
                text=f"{key}:",
                fill="#888888",
                font=(cfg.font_family, 9),
                anchor="w",
                tags="stats"
            )
            # Değer
            c.create_text(
                cx + 55, cy,
                text=value,
                fill=cfg.text_color,
                font=(cfg.font_family, 10, "bold"),
                anchor="w",
                tags="stats"
            )

        rows = (len(stats) + 2) // 3
        return y + rows * 30 + 10

    def _draw_primary_advice(self, c, cfg, y, advice: AdvicePackage) -> int:
        """Ana öneriyi çizer."""
        if not advice.primary_advice:
            return y

        adv = advice.primary_advice

        # Ayırıcı
        c.create_line(10, y, cfg.width - 10, y, fill="#333333", tags="advice")
        y += 10

        # Aksiyon rengi
        action_colors = {
            "FOLD": "#ff6b6b",
            "CHECK": "#ffd93d",
            "CALL": "#51cf66",
            "BET": "#00d4ff",
            "RAISE": "#ff922b",
            "ALL_IN": "#ff00ff",
        }
        action_color = action_colors.get(adv.action, cfg.text_color)

        # Büyük aksiyon etiketi
        action_text = adv.action
        if adv.amount > 0:
            action_text += f"  ${adv.amount:.2f}"

        c.create_text(
            cfg.width // 2, y + 5,
            text="ÖNERİ",
            fill="#888888",
            font=(cfg.font_family, 9),
            anchor="center",
            tags="advice"
        )

        c.create_text(
            cfg.width // 2, y + 30,
            text=action_text,
            fill=action_color,
            font=(cfg.font_family, 18, "bold"),
            anchor="center",
            tags="advice"
        )

        # Açıklama
        if adv.description:
            c.create_text(
                cfg.width // 2, y + 55,
                text=adv.description,
                fill="#aaaaaa",
                font=(cfg.font_family, 10),
                anchor="center",
                tags="advice"
            )
            return y + 75

        return y + 55

    def _draw_hand_info(self, c, cfg, y, advice: AdvicePackage) -> int:
        """El bilgisini çizer."""
        # Ayırıcı
        c.create_line(10, y, cfg.width - 10, y, fill="#333333", tags="info")
        y += 10

        # El kategorisi
        c.create_text(
            15, y,
            text="El:",
            fill="#888888",
            font=(cfg.font_family, 9),
            anchor="w",
            tags="info"
        )
        c.create_text(
            50, y,
            text=advice.hand_category or "?",
            fill=cfg.text_color,
            font=(cfg.font_family, 10, "bold"),
            anchor="w",
            tags="info"
        )

        # Güç etiketi
        strength_colors = {
            "Çok Güçlü": "#00ff00",
            "Güçlü": "#51cf66",
            "Orta-Güçlü": "#ffd93d",
            "Orta": "#ff922b",
            "Zayıf": "#ff6b6b",
            "Çok Zayıf": "#ff0000",
        }
        strength_color = strength_colors.get(advice.hand_strength_label, cfg.text_color)

        c.create_text(
            cfg.width - 15, y,
            text=advice.hand_strength_label,
            fill=strength_color,
            font=(cfg.font_family, 10, "bold"),
            anchor="e",
            tags="info"
        )
        y += 20

        # Equity
        c.create_text(
            15, y,
            text=f"Equity: %{advice.equity_percent:.1f}",
            fill=cfg.accent_color,
            font=(cfg.font_family, 10),
            anchor="w",
            tags="info"
        )

        # Pot Odds
        if advice.pot_odds_percent > 0:
            c.create_text(
                cfg.width // 2, y,
                text=f"Pot Odds: %{advice.pot_odds_percent:.1f}",
                fill=cfg.text_color,
                font=(cfg.font_family, 10),
                anchor="w",
                tags="info"
            )

        # SPR
        if advice.spr < float('inf'):
            c.create_text(
                cfg.width - 15, y,
                text=f"SPR: {advice.spr:.1f}",
                fill=cfg.text_color,
                font=(cfg.font_family, 10),
                anchor="e",
                tags="info"
            )

        return y + 25

    def _draw_board_info(self, c, cfg, y, advice: AdvicePackage) -> int:
        """Board bilgisini çizer."""
        if not advice.board_texture:
            return y

        # Ayırıcı
        c.create_line(10, y, cfg.width - 10, y, fill="#333333", tags="board")
        y += 10

        # Board texture
        c.create_text(
            15, y,
            text="Board:",
            fill="#888888",
            font=(cfg.font_family, 9),
            anchor="w",
            tags="board"
        )
        c.create_text(
            65, y,
            text=advice.board_texture,
            fill=cfg.text_color,
            font=(cfg.font_family, 10),
            anchor="w",
            tags="board"
        )

        # Tehlike seviyesi (renk kodlu)
        danger = advice.board_danger
        if danger <= 3:
            danger_color = "#51cf66"  # Yeşil - güvenli
        elif danger <= 6:
            danger_color = "#ffd93d"  # Sarı - orta
        else:
            danger_color = "#ff6b6b"  # Kırmızı - tehlikeli

        # Tehlike barı
        bar_x = cfg.width - 120
        bar_width = 100
        bar_height = 12

        # Arkaplan
        c.create_rectangle(
            bar_x, y - 6, bar_x + bar_width, y + bar_height - 6,
            fill="#333333", outline="",
            tags="board"
        )
        # Dolu kısım
        fill_width = int(bar_width * danger / 10)
        if fill_width > 0:
            c.create_rectangle(
                bar_x, y - 6, bar_x + fill_width, y + bar_height - 6,
                fill=danger_color, outline="",
                tags="board"
            )
        # Etiket
        c.create_text(
            bar_x + bar_width // 2, y,
            text=f"{danger}/10",
            fill="white",
            font=(cfg.font_family, 8, "bold"),
            anchor="center",
            tags="board"
        )

        y += 20

        # Board açıklaması
        if advice.board_description:
            c.create_text(
                15, y,
                text=advice.board_description,
                fill="#aaaaaa",
                font=(cfg.font_family, 9),
                anchor="w",
                width=cfg.width - 30,
                tags="board"
            )
            y += 20

        return y + 5

    def _draw_draw_info(self, c, cfg, y, advice: AdvicePackage) -> int:
        """Draw bilgisini çizer."""
        c.create_line(10, y, cfg.width - 10, y, fill="#333333", tags="draw")
        y += 10

        c.create_text(
            15, y,
            text=f"Draw: {advice.draw_description}",
            fill="#ffd93d",
            font=(cfg.font_family, 10, "bold"),
            anchor="w",
            tags="draw"
        )
        c.create_text(
            cfg.width - 15, y,
            text=f"{advice.draw_outs} Out",
            fill="#ffd93d",
            font=(cfg.font_family, 10),
            anchor="e",
            tags="draw"
        )

        return y + 25

    def _draw_reasoning(self, c, cfg, y, advice: AdvicePackage) -> int:
        """Karar gerekçesini çizer."""
        if not advice.primary_advice:
            return y

        c.create_line(10, y, cfg.width - 10, y, fill="#333333", tags="info")
        y += 10

        reasoning = advice.primary_advice.reasoning
        # Satırlara böl
        parts = reasoning.split(" | ")

        for part in parts:
            c.create_text(
                15, y,
                text=f"• {part}",
                fill="#888888",
                font=(cfg.font_family, 9),
                anchor="w",
                width=cfg.width - 30,
                tags="info"
            )
            y += 16

        return y + 5

    def stop(self) -> None:
        """Overlay penceresini kapat."""
        self._running = False
        if self._root:
            try:
                self._root.quit()
                self._root.destroy()
            except Exception:
                pass
            self._root = None

    @property
    def is_running(self) -> bool:
        return self._running


class ConsoleOverlay:
    """
    Terminal tabanlı overlay alternatifi.
    GUI olmadan çalışır, bilgileri konsola yazdırır.
    """

    def __init__(self):
        self._running = False

    def start(self) -> None:
        self._running = True
        print("\n" + "=" * 60)
        print("  POKER TRACKER - Console Mode")
        print("=" * 60)

    def update(self, advice: AdvicePackage, quick_stats: Dict[str, str]) -> None:
        if not self._running:
            return

        # Ekranı temizle (ANSI escape)
        print("\033[2J\033[H", end="")

        print("╔" + "═" * 58 + "╗")
        print("║" + "  POKER TRACKER".center(58) + "║")
        print("╠" + "═" * 58 + "╣")

        # Quick stats
        stats_line = "  ".join(f"{k}: {v}" for k, v in quick_stats.items())
        print(f"║ {stats_line:<57}║")
        print("╠" + "═" * 58 + "╣")

        # Ana öneri
        if advice.primary_advice:
            adv = advice.primary_advice
            action_str = adv.action
            if adv.amount > 0:
                action_str += f" ${adv.amount:.2f}"

            print(f"║ {'ÖNERİ:':>10} {action_str:<47}║")
            if adv.description:
                print(f"║ {'':>10} {adv.description:<47}║")
            print("╠" + "═" * 58 + "╣")

        # El bilgisi
        print(f"║ {'El:':>10} {advice.hand_category:<20} {advice.hand_strength_label:<26}║")
        print(f"║ {'Equity:':>10} %{advice.equity_percent:<6.1f} {'Pot Odds:':>12} %{advice.pot_odds_percent:<6.1f} {'SPR:':>6} {advice.spr:<6.1f}║")

        # Board
        if advice.board_texture:
            print(f"║ {'Board:':>10} {advice.board_texture:<20} Tehlike: {advice.board_danger}/10{' ' * 16}║")

        # Draw
        if advice.has_draw:
            print(f"║ {'Draw:':>10} {advice.draw_description:<20} {advice.draw_outs} out{' ' * 22}║")

        # Reasoning
        if advice.primary_advice and advice.primary_advice.reasoning:
            print("╠" + "═" * 58 + "╣")
            parts = advice.primary_advice.reasoning.split(" | ")
            for part in parts:
                print(f"║  • {part:<55}║")

        print("╚" + "═" * 58 + "╝")

    def stop(self) -> None:
        self._running = False
        print("\nPoker Tracker durduruldu.")

    @property
    def is_running(self) -> bool:
        return self._running
