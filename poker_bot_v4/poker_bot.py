"""
POKER BOT V4.0 - MAIN BOT CLASS
================================
Ana bot sınıfı - tüm modülleri birleştirir.
"""

import logging
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from constants import Position, Street, ActionType, BoardTexture
from data_classes import (
    Card, HoleCards, Board, GameState, PokerAction,
    HandStrength, BoardAnalysis, PlayerStats
)
from hand_evaluator import HandEvaluator, BoardAnalyzer
from strategy import PreflopStrategy, PostflopStrategy, BetSizer
from anti_detection import (
    HumanTimer, MistakeMaker, BettingPatternVariator, 
    SessionManager, TimingConfig
)

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger("PokerBot_v4")


@dataclass
class BotConfig:
    """Bot konfigürasyonu."""
    # Oyun ayarları
    small_blind: float = 0.50
    big_blind: float = 1.00
    starting_stack: float = 100.0  # BB cinsinden
    
    # Strateji ayarları
    play_style: str = "balanced"  # "balanced", "aggressive", "tight"
    use_exploits: bool = True     # Rakip bazlı ayarlama
    
    # Anti-detection
    use_human_timing: bool = True
    mistake_probability: float = 0.03
    vary_bet_sizes: bool = True
    
    # Debug
    verbose: bool = False


class PokerBot:
    """
    Ana Poker Bot sınıfı.
    
    Kullanım:
        bot = PokerBot(config)
        bot.new_hand(hero_cards, position)
        action = bot.decide(game_state)
    """
    
    def __init__(self, config: Optional[BotConfig] = None):
        self.config = config or BotConfig()
        
        # Core components
        self.evaluator = HandEvaluator()
        self.board_analyzer = BoardAnalyzer()
        
        # Strategy
        self.preflop_strategy = PreflopStrategy()
        self.postflop_strategy = PostflopStrategy()
        
        # Anti-detection
        timing_cfg = TimingConfig() if self.config.use_human_timing else None
        self.timer = HumanTimer(timing_cfg)
        self.mistake_maker = MistakeMaker(self.config.mistake_probability)
        self.bet_variator = BettingPatternVariator()
        self.session = SessionManager()
        
        # State
        self.current_hand: Optional[HoleCards] = None
        self.current_position: Optional[Position] = None
        self.hand_history: List[Dict[str, Any]] = []
        
        # Opponent tracking
        self.opponent_stats: Dict[str, PlayerStats] = {}
        
        log.info("PokerBot V4.0 initialized")
        log.info(f"Config: {self.config}")
    
    def new_hand(
        self, 
        hole_cards: List[str],
        position: Position,
        villain_id: Optional[str] = None
    ) -> None:
        """
        Yeni el başlat.
        
        Args:
            hole_cards: ["Ah", "Kc"] formatında kartlar
            position: Hero'nun pozisyonu
            villain_id: Rakip ID (stats için)
        """
        self.current_hand = HoleCards.from_strings(hole_cards)
        self.current_position = position
        
        log.info(f"New hand: {self.current_hand} from {position.name}")
        
        # Rakip stats
        if villain_id and villain_id in self.opponent_stats:
            self._current_villain = self.opponent_stats[villain_id]
        else:
            self._current_villain = None
    
    def decide(self, state: GameState) -> PokerAction:
        """
        Mevcut durum için en iyi aksiyonu belirler.
        
        Args:
            state: Oyunun anlık durumu
            
        Returns:
            PokerAction: Yapılacak aksiyon
        """
        if self.current_hand is None:
            raise ValueError("new_hand() çağrılmalı önce")
        
        # State'e hero bilgilerini ekle
        state.hero_hand = self.current_hand
        state.hero_position = self.current_position
        state.villain_stats = self._current_villain
        
        # Karar
        if state.street == Street.PREFLOP:
            action = self.preflop_strategy.decide(state)
        else:
            action = self.postflop_strategy.decide(state)
        
        # Mistake check
        if self.mistake_maker.should_make_mistake():
            mistake_type = self.mistake_maker.get_mistake_type()
            action = self.mistake_maker.apply_mistake(action, state.pot, mistake_type)
            log.debug(f"Mistake applied: {mistake_type.name}")
        
        # Bet size varyasyonu
        if self.config.vary_bet_sizes and action.amount > 0:
            action.amount = self.bet_variator.vary_bet_size(action.amount, state.pot)
            action.amount = self.bet_variator.round_to_human_amount(action.amount)
        
        # Timing
        is_difficult = self._is_difficult_spot(state, action)
        think_time = self.timer.get_think_time(
            state.street, 
            is_difficult=is_difficult,
            action_type=action.action
        )
        
        log.info(f"Decision: {action} (think time: {think_time}s)")
        
        # Timing simülasyonu (gerçek kullanımda)
        if self.config.use_human_timing:
            time.sleep(think_time)
        
        # Session tracking
        self.session.record_hand()
        
        return action
    
    def end_hand(self, won: bool, pot_size: float, was_bad_beat: bool = False):
        """
        El bitti, sonucu kaydet.
        
        Args:
            won: Kazandık mı?
            pot_size: Pot büyüklüğü
            was_bad_beat: Bad beat mi?
        """
        self.session.record_hand(won, pot_size)
        self.timer.update_tilt(lost_pot=not won, bad_beat=was_bad_beat)
        
        # History'e ekle
        self.hand_history.append({
            "hand": str(self.current_hand),
            "position": self.current_position.name if self.current_position else None,
            "won": won,
            "pot": pot_size
        })
        
        # Reset
        self.current_hand = None
        self.current_position = None
    
    def update_opponent_stats(self, villain_id: str, stats: PlayerStats):
        """Rakip istatistiklerini güncelle."""
        self.opponent_stats[villain_id] = stats
        log.debug(f"Updated stats for {villain_id}: {stats.player_type}")
    
    def _is_difficult_spot(self, state: GameState, action: PokerAction) -> bool:
        """Zor karar mı?"""
        # All-in kararları zor
        if action.action == ActionType.ALL_IN:
            return True
        
        # Büyük pot (10+ BB)
        if state.pot > state.big_blind * 10:
            return True
        
        # River bluff/call
        if state.street == Street.RIVER:
            if action.action in [ActionType.BET, ActionType.RAISE]:
                return True
            if action.action == ActionType.CALL and state.current_bet > state.pot * 0.5:
                return True
        
        return False
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Session istatistiklerini döndür."""
        return {
            "hands_played": self.session.hands_played,
            "session_duration_min": round(self.session.session_duration_minutes, 1),
            "is_fatigued": self.session.is_fatigued,
            "tilt_level": round(self.timer.tilt_level, 2),
            "mistake_stats": self.mistake_maker.get_stats(),
            "big_pots": {
                "won": self.session.big_pots_won,
                "lost": self.session.big_pots_lost
            }
        }
    
    def reset_session(self):
        """Session'ı sıfırla."""
        self.session = SessionManager()
        self.timer.reset_session()
        self.hand_history = []
        log.info("Session reset")
