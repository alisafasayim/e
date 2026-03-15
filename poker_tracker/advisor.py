"""
POKER TRACKER - STRATEGY ADVISOR
==================================
Mevcut poker_bot_v4 strateji motorunu kullanarak
canlı öneriler sunan danışman modülü.
"""

import logging
import sys
import os
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field

# poker_bot_v4 modüllerine erişim
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'poker_bot_v4'))

try:
    from strategy import PreflopStrategy, PostflopStrategy, BetSizer
    from hand_evaluator import HandEvaluator, BoardAnalyzer
    from data_classes import GameState, PokerAction, HandStrength, BoardAnalysis
    from constants import Street, ActionType, Position
    STRATEGY_AVAILABLE = True
except ImportError:
    STRATEGY_AVAILABLE = False
    logging.warning("poker_bot_v4 strateji modülleri bulunamadı.")

from game_state_tracker import TrackedGameState

log = logging.getLogger("Advisor")


@dataclass
class StreetAdvice:
    """Bir sokak için strateji önerisi."""
    action: str = ""            # FOLD, CHECK, CALL, BET, RAISE, ALL_IN
    amount: float = 0.0
    description: str = ""
    confidence: float = 0.0     # 0-1

    # Detaylı bilgi
    equity: float = 0.0
    pot_odds: float = 0.0
    hand_description: str = ""
    board_description: str = ""
    reasoning: str = ""


@dataclass
class AdvicePackage:
    """
    Overlay'de gösterilecek tam öneri paketi.
    """
    # Ana öneri
    primary_advice: Optional[StreetAdvice] = None

    # El bilgisi
    hand_category: str = ""         # "Top Pair", "Flush Draw" vb.
    hand_strength_label: str = ""   # "Güçlü", "Orta", "Zayıf"
    equity_percent: float = 0.0

    # Board bilgisi
    board_texture: str = ""         # "Kuru", "Islak", "Monotone" vb.
    board_danger: int = 0           # 0-10
    board_description: str = ""

    # Pot bilgisi
    pot_size: float = 0.0
    pot_odds_percent: float = 0.0
    spr: float = 0.0

    # Pozisyon bilgisi
    position: str = ""
    position_advantage: str = ""    # "IP" veya "OOP"

    # Draw bilgisi
    has_draw: bool = False
    draw_description: str = ""
    draw_outs: int = 0

    # Range bilgisi
    range_advice: str = ""          # "RFI Range'de", "3-Bet Range'de" vb.

    # Genel notlar
    notes: List[str] = field(default_factory=list)


class StrategyAdvisor:
    """
    Canlı strateji danışmanı.
    Ekrandan okunan duruma göre öneriler üretir.
    """

    def __init__(self):
        if STRATEGY_AVAILABLE:
            self._preflop = PreflopStrategy()
            self._postflop = PostflopStrategy()
            self._evaluator = HandEvaluator()
            self._board_analyzer = BoardAnalyzer()
            self._bet_sizer = BetSizer()
        else:
            self._preflop = None
            self._postflop = None
            self._evaluator = None
            self._board_analyzer = None
            self._bet_sizer = None

    def analyze(self, tracked_state: TrackedGameState, game_state: Optional['GameState'] = None) -> AdvicePackage:
        """
        Anlık durumu analiz eder ve öneri paketi üretir.
        """
        package = AdvicePackage()

        # Temel bilgileri doldur
        package.pot_size = tracked_state.pot
        package.position = tracked_state.hero_position
        package.position_advantage = self._get_position_advantage(tracked_state)

        if not STRATEGY_AVAILABLE or game_state is None:
            package.notes.append("Strateji motoru yüklenemedi")
            return package

        # SPR
        package.spr = game_state.spr

        # Pot odds
        package.pot_odds_percent = game_state.pot_odds * 100

        # El analizi
        if game_state.hero_hand and game_state.board:
            self._analyze_hand(game_state, package)

        # Board analizi
        if game_state.board and len(game_state.board.cards) > 0:
            self._analyze_board(game_state, package)

        # Strateji önerisi
        advice = self._get_advice(game_state, package)
        package.primary_advice = advice

        return package

    def _analyze_hand(self, state: GameState, package: AdvicePackage) -> None:
        """El gücünü analiz eder."""
        try:
            strength = self._evaluator.evaluate_hand(state.hero_hand, state.board)

            package.equity_percent = strength.equity * 100
            package.hand_category = strength.made_hand_desc or strength.hand_category.name
            package.hand_strength_label = self._get_strength_label(strength.equity)

            # Draw bilgisi
            if strength.has_draw:
                package.has_draw = True
                package.draw_description = strength.draw_type.name
                package.draw_outs = strength.draw_outs

        except Exception as e:
            log.error(f"El analizi hatası: {e}")

    def _analyze_board(self, state: GameState, package: AdvicePackage) -> None:
        """Board dokusunu analiz eder."""
        try:
            analysis = self._board_analyzer.analyze(state.board)

            package.board_texture = analysis.texture.name
            package.board_danger = analysis.danger_level
            package.board_description = analysis.description

        except Exception as e:
            log.error(f"Board analizi hatası: {e}")

    def _get_advice(self, state: GameState, package: AdvicePackage) -> StreetAdvice:
        """Ana strateji önerisini üretir."""
        advice = StreetAdvice()

        try:
            if state.street == Street.PREFLOP:
                action = self._preflop.decide(state)
            else:
                action = self._postflop.decide(state)

            advice.action = action.action.value
            advice.amount = action.amount
            advice.description = action.description
            advice.confidence = action.confidence
            advice.equity = package.equity_percent / 100
            advice.pot_odds = package.pot_odds_percent / 100

            # Reasoning
            advice.reasoning = self._build_reasoning(state, action, package)

        except Exception as e:
            log.error(f"Strateji önerisi hatası: {e}")
            advice.action = "?"
            advice.description = f"Hata: {str(e)}"

        return advice

    def _build_reasoning(self, state: GameState, action: PokerAction, package: AdvicePackage) -> str:
        """Karar gerekçesi oluşturur."""
        parts = []

        # Pozisyon
        parts.append(f"Pozisyon: {package.position} ({package.position_advantage})")

        # El gücü
        if package.equity_percent > 0:
            parts.append(f"Equity: %{package.equity_percent:.1f}")

        # Pot odds
        if package.pot_odds_percent > 0:
            parts.append(f"Pot Odds: %{package.pot_odds_percent:.1f}")

        # SPR
        if package.spr < float('inf'):
            parts.append(f"SPR: {package.spr:.1f}")

        # Draw
        if package.has_draw:
            parts.append(f"Draw: {package.draw_description} ({package.draw_outs} out)")

        # Board
        if package.board_danger > 0:
            parts.append(f"Board Tehlike: {package.board_danger}/10")

        return " | ".join(parts)

    def _get_strength_label(self, equity: float) -> str:
        """Equity'ye göre el gücü etiketi."""
        if equity >= 0.80:
            return "Çok Güçlü"
        elif equity >= 0.65:
            return "Güçlü"
        elif equity >= 0.50:
            return "Orta-Güçlü"
        elif equity >= 0.35:
            return "Orta"
        elif equity >= 0.20:
            return "Zayıf"
        else:
            return "Çok Zayıf"

    def _get_position_advantage(self, state: TrackedGameState) -> str:
        """Pozisyon avantajını belirler."""
        ip_positions = {"BTN", "CO"}
        if state.hero_position in ip_positions:
            return "IP"   # In Position
        else:
            return "OOP"  # Out of Position

    def get_quick_stats(self, tracked_state: TrackedGameState) -> Dict[str, str]:
        """
        Hızlı istatistik özeti (overlay'in üst kısmında gösterilecek).
        """
        stats = {}

        # El numarası
        stats["El"] = f"#{tracked_state.hand_number}"

        # Sokak
        stats["Sokak"] = tracked_state.street

        # Pot
        stats["Pot"] = f"${tracked_state.pot:.2f}"

        # Pozisyon
        stats["Pozisyon"] = tracked_state.hero_position or "?"

        # Stack
        stats["Stack"] = f"${tracked_state.hero_stack:.2f}"

        # Aktif oyuncu
        stats["Oyuncu"] = str(tracked_state.num_active_players)

        return stats
