"""
POKER TRACKER - GAME STATE TRACKER
====================================
Ekrandan okunan bilgileri oyun durumuna dönüştürür.
Değişiklikleri algılar ve oyun akışını takip eder.
"""

import logging
import time
import sys
import os
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass, field

import numpy as np

# Mevcut poker_bot_v4 modüllerine erişim
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'poker_bot_v4'))

from screen_capture import ScreenCapture, MockScreenCapture
from card_detector import CardDetector, DetectedCard
from ocr_engine import OCREngine
from config import TrackerConfig, ScreenRegion

# poker_bot_v4 veri yapıları
try:
    from data_classes import Card, HoleCards, Board, GameState, PokerAction
    from constants import Position, Street, ActionType
    BOT_AVAILABLE = True
except ImportError:
    BOT_AVAILABLE = False
    logging.warning("poker_bot_v4 modülleri bulunamadı. Strateji önerileri devre dışı.")

log = logging.getLogger("GameStateTracker")


POSITION_NAMES = {
    0: "BTN", 1: "SB", 2: "BB", 3: "UTG", 4: "MP", 5: "CO"
}

POSITION_MAP = {
    "BTN": Position.BTN if BOT_AVAILABLE else 3,
    "SB": Position.SB if BOT_AVAILABLE else 4,
    "BB": Position.BB if BOT_AVAILABLE else 5,
    "UTG": Position.UTG if BOT_AVAILABLE else 0,
    "MP": Position.MP if BOT_AVAILABLE else 1,
    "CO": Position.CO if BOT_AVAILABLE else 2,
}


@dataclass
class PlayerState:
    """Bir oyuncunun anlık durumu."""
    seat: int = 0
    name: str = ""
    stack: float = 0.0
    current_bet: float = 0.0
    is_active: bool = True
    is_dealer: bool = False
    position: str = ""


@dataclass
class TrackedGameState:
    """
    Tracker'ın takip ettiği tam oyun durumu.
    Her ekran taramasında güncellenir.
    """
    # El bilgisi
    hand_number: int = 0
    timestamp: float = 0.0

    # Kartlar
    hero_cards: List[Optional[DetectedCard]] = field(default_factory=list)
    board_cards: List[Optional[DetectedCard]] = field(default_factory=list)

    # Sokak
    street: str = "PREFLOP"  # PREFLOP, FLOP, TURN, RIVER

    # Pot ve bet
    pot: float = 0.0
    total_pot: float = 0.0  # Side pot dahil

    # Oyuncular
    players: List[PlayerState] = field(default_factory=list)
    hero_seat: int = 0
    dealer_seat: int = -1

    # Pozisyon
    hero_position: str = ""
    num_active_players: int = 0

    # Aksiyon geçmişi
    available_actions: List[str] = field(default_factory=list)
    last_action: str = ""

    # Durum bayrakları
    is_hero_turn: bool = False
    hand_complete: bool = False

    @property
    def hero_stack(self) -> float:
        for p in self.players:
            if p.seat == self.hero_seat:
                return p.stack
        return 0.0

    @property
    def hero_bet(self) -> float:
        for p in self.players:
            if p.seat == self.hero_seat:
                return p.current_bet
        return 0.0

    @property
    def board_card_count(self) -> int:
        return len([c for c in self.board_cards if c is not None])

    @property
    def has_hero_cards(self) -> bool:
        return len([c for c in self.hero_cards if c is not None]) == 2

    def to_game_state(self, config: TrackerConfig) -> Optional['GameState']:
        """poker_bot_v4 GameState'e dönüştür."""
        if not BOT_AVAILABLE:
            return None

        if not self.has_hero_cards:
            return None

        # Hero kartları
        hero_card_notations = [c.notation for c in self.hero_cards if c is not None]
        if len(hero_card_notations) != 2:
            return None

        hero_hand = HoleCards.from_strings(hero_card_notations)

        # Board
        board_notations = [c.notation for c in self.board_cards if c is not None]
        board = Board.from_strings(board_notations)

        # Street
        street_map = {
            "PREFLOP": Street.PREFLOP,
            "FLOP": Street.FLOP,
            "TURN": Street.TURN,
            "RIVER": Street.RIVER,
        }
        street = street_map.get(self.street, Street.PREFLOP)

        # Pozisyon
        hero_pos = POSITION_MAP.get(self.hero_position, Position.BB)

        # En büyük bet'i olan rakibi bul
        max_bet = 0.0
        villain_seat = -1
        for p in self.players:
            if p.seat != self.hero_seat and p.current_bet > max_bet and p.is_active:
                max_bet = p.current_bet
                villain_seat = p.seat

        villain_pos = Position.BTN  # Default
        for p in self.players:
            if p.seat == villain_seat and p.position:
                villain_pos = POSITION_MAP.get(p.position, Position.BTN)

        # Villain stack
        villain_stack = 100.0
        for p in self.players:
            if p.seat == villain_seat:
                villain_stack = p.stack

        return GameState(
            street=street,
            hero_hand=hero_hand,
            board=board,
            hero_position=hero_pos,
            villain_position=villain_pos,
            hero_stack=self.hero_stack,
            villain_stack=villain_stack,
            pot=self.pot,
            current_bet=max_bet,
            hero_invested=self.hero_bet,
            villain_invested=max_bet,
            small_blind=config.small_blind,
            big_blind=config.big_blind,
        )


class GameStateTracker:
    """
    Ana oyun durumu takipçisi.
    Ekranı periyodik olarak tarar ve durumu günceller.
    """

    def __init__(self, config: TrackerConfig, use_mock: bool = False):
        self.config = config

        # Alt modüller
        if use_mock:
            self._capture = MockScreenCapture()
        else:
            self._capture = ScreenCapture()

        self._card_detector = CardDetector()
        self._ocr = OCREngine(config.ocr_config)

        # Durum
        self._current_state = TrackedGameState(
            hero_seat=config.hero_seat,
            players=[PlayerState(seat=i) for i in range(config.num_seats)]
        )
        self._previous_state: Optional[TrackedGameState] = None
        self._hand_history: List[TrackedGameState] = []

        # Değişiklik algılama
        self._last_board_cards: List[str] = []
        self._last_pot: float = 0.0
        self._state_change_callbacks: List = []

    @property
    def current_state(self) -> TrackedGameState:
        return self._current_state

    def register_callback(self, callback) -> None:
        """Durum değişikliği callback'i kaydet."""
        self._state_change_callbacks.append(callback)

    def scan(self) -> TrackedGameState:
        """
        Ekranı tarar ve oyun durumunu günceller.
        Bu metod her tarama döngüsünde çağrılır.
        """
        layout = self.config.table_layout

        # 1. Board kartlarını tara
        self._scan_board_cards(layout)

        # 2. Hero kartlarını tara
        self._scan_hero_cards(layout)

        # 3. Pot miktarını oku
        self._scan_pot(layout)

        # 4. Bet miktarlarını oku
        self._scan_bets(layout)

        # 5. Stack bilgilerini oku
        self._scan_stacks(layout)

        # 6. Dealer button'ı bul
        self._scan_dealer_button(layout)

        # 7. Pozisyonları hesapla
        self._calculate_positions()

        # 8. Sokağı belirle
        self._determine_street()

        # 9. Aksiyon butonlarını kontrol et
        self._scan_action_buttons(layout)

        # 10. Değişiklikleri algıla
        self._detect_changes()

        # Timestamp güncelle
        self._current_state.timestamp = time.time()

        return self._current_state

    def _scan_board_cards(self, layout) -> None:
        """Board kartlarını tarar."""
        card_images = self._capture.capture_multiple_regions(layout.board_cards)
        detected = self._card_detector.detect_board_cards(card_images)
        self._current_state.board_cards = detected

    def _scan_hero_cards(self, layout) -> None:
        """Hero kartlarını tarar."""
        card_images = self._capture.capture_multiple_regions(layout.hero_cards)
        detected = self._card_detector.detect_hero_cards(card_images)
        self._current_state.hero_cards = detected

    def _scan_pot(self, layout) -> None:
        """Pot miktarını okur."""
        pot_img = self._capture.capture_region(layout.pot_region)
        pot = self._ocr.read_pot(pot_img)
        if pot is not None and pot >= 0:
            self._current_state.pot = pot

    def _scan_bets(self, layout) -> None:
        """Her oyuncunun bet miktarını okur."""
        for i, region in enumerate(layout.bet_regions):
            if i >= len(self._current_state.players):
                break
            bet_img = self._capture.capture_region(region)
            bet = self._ocr.read_bet(bet_img)
            if bet is not None and bet >= 0:
                self._current_state.players[i].current_bet = bet
            else:
                self._current_state.players[i].current_bet = 0.0

    def _scan_stacks(self, layout) -> None:
        """Her oyuncunun stack miktarını okur."""
        for i, region in enumerate(layout.stack_regions):
            if i >= len(self._current_state.players):
                break
            stack_img = self._capture.capture_region(region)
            stack = self._ocr.read_stack(stack_img)
            if stack is not None and stack >= 0:
                self._current_state.players[i].stack = stack

    def _scan_dealer_button(self, layout) -> None:
        """Dealer button'ı bulur."""
        for i, region in enumerate(layout.dealer_button_regions):
            if i >= len(self._current_state.players):
                break
            btn_img = self._capture.capture_region(region)
            is_dealer = self._ocr.detect_dealer_button(btn_img)

            self._current_state.players[i].is_dealer = is_dealer
            if is_dealer:
                self._current_state.dealer_seat = i

    def _calculate_positions(self) -> None:
        """Dealer button'a göre pozisyonları hesaplar."""
        dealer = self._current_state.dealer_seat
        if dealer < 0:
            return

        num_seats = self.config.num_seats
        hero_seat = self.config.hero_seat

        # Aktif oyuncu sayısı
        active_players = [
            p for p in self._current_state.players
            if p.is_active and (p.stack > 0 or p.current_bet > 0)
        ]
        num_active = len(active_players)
        self._current_state.num_active_players = num_active

        if num_active == 0:
            return

        # Pozisyon atama (BTN'den saat yönünde: SB, BB, UTG, MP, CO)
        positions_6max = ["BTN", "SB", "BB", "UTG", "MP", "CO"]
        positions_short = {
            2: ["BTN", "BB"],
            3: ["BTN", "SB", "BB"],
            4: ["BTN", "SB", "BB", "CO"],
            5: ["BTN", "SB", "BB", "UTG", "CO"],
            6: ["BTN", "SB", "BB", "UTG", "MP", "CO"],
        }

        pos_list = positions_short.get(num_active, positions_6max)

        # Dealer'dan başlayarak aktif oyunculara pozisyon ata
        active_seats = sorted([p.seat for p in active_players])

        # Dealer seat'ten başla
        start_idx = 0
        for idx, seat in enumerate(active_seats):
            if seat == dealer:
                start_idx = idx
                break

        for pos_idx, pos_name in enumerate(pos_list):
            seat_idx = (start_idx + pos_idx) % len(active_seats)
            seat = active_seats[seat_idx]

            for p in self._current_state.players:
                if p.seat == seat:
                    p.position = pos_name

            if seat == hero_seat:
                self._current_state.hero_position = pos_name

    def _determine_street(self) -> None:
        """Board kart sayısına göre sokağı belirler."""
        board_count = self._current_state.board_card_count

        if board_count == 0:
            self._current_state.street = "PREFLOP"
        elif board_count == 3:
            self._current_state.street = "FLOP"
        elif board_count == 4:
            self._current_state.street = "TURN"
        elif board_count >= 5:
            self._current_state.street = "RIVER"

    def _scan_action_buttons(self, layout) -> None:
        """Aksiyon butonlarını kontrol eder."""
        btn_img = self._capture.capture_region(layout.action_buttons_region)
        actions = self._ocr.detect_action_buttons(btn_img)
        self._current_state.available_actions = actions
        self._current_state.is_hero_turn = len(actions) > 0

    def _detect_changes(self) -> None:
        """Önceki durumla karşılaştırarak değişiklikleri algılar."""
        # Board kartı değişikliği
        current_board = [
            c.notation for c in self._current_state.board_cards if c is not None
        ]

        if current_board != self._last_board_cards:
            if len(current_board) > len(self._last_board_cards):
                new_cards = current_board[len(self._last_board_cards):]
                log.info(f"Yeni board kartları: {new_cards}")

                # Yeni el kontrolü
                if len(self._last_board_cards) > 0 and len(current_board) < len(self._last_board_cards):
                    self._on_new_hand()

            self._last_board_cards = current_board

        # Pot değişikliği
        if abs(self._current_state.pot - self._last_pot) > 0.01:
            log.debug(f"Pot değişti: ${self._last_pot:.2f} -> ${self._current_state.pot:.2f}")
            self._last_pot = self._current_state.pot

        # Callback'leri çağır
        for callback in self._state_change_callbacks:
            try:
                callback(self._current_state)
            except Exception as e:
                log.error(f"Callback hatası: {e}")

    def _on_new_hand(self) -> None:
        """Yeni el başladığında çağrılır."""
        self._current_state.hand_number += 1
        self._current_state.hand_complete = False

        # Önceki durumu geçmişe ekle
        if self._previous_state:
            self._hand_history.append(self._previous_state)

        # Betleri sıfırla
        for p in self._current_state.players:
            p.current_bet = 0.0

        log.info(f"=== YENİ EL #{self._current_state.hand_number} ===")

    def get_game_state(self) -> Optional['GameState']:
        """poker_bot_v4 uyumlu GameState döndürür."""
        return self._current_state.to_game_state(self.config)

    def get_hand_history(self) -> List[TrackedGameState]:
        """El geçmişini döndürür."""
        return self._hand_history.copy()

    def close(self) -> None:
        """Kaynakları serbest bırak."""
        self._capture.close()
