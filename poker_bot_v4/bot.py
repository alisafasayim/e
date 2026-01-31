"""
POKER BOT V4.0 - MAIN BOT
=========================
Ana bot sınıfı ve oyun kontrolcüsü.
"""

import logging
from typing import Optional, List, Tuple
from dataclasses import dataclass

from constants import Position, Street, ActionType
from data_classes import (
    Card, HoleCards, Board, GameState, PokerAction, 
    HandStrength, BoardAnalysis, PlayerStats
)
from hand_evaluator import HandEvaluator, BoardAnalyzer
from strategy import PreflopStrategy, PostflopStrategy
from anti_detection import AntiDetectionSystem, TimingConfig

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
    default_stack: float = 100.0
    
    # Strateji ayarları
    aggression: float = 0.6       # 0.0 (pasif) - 1.0 (maniac)
    bluff_frequency: float = 0.20 # Bluff sıklığı
    
    # Anti-Detection
    use_anti_detection: bool = True
    mistake_probability: float = 0.03
    timing_variance: float = 0.15
    
    # Debug
    verbose: bool = False


class PokerBot:
    """
    Ana poker botu.
    Tüm bileşenleri koordine eder.
    """
    
    def __init__(self, config: Optional[BotConfig] = None):
        self.config = config or BotConfig()
        
        # Bileşenler
        self.evaluator = HandEvaluator()
        self.board_analyzer = BoardAnalyzer()
        self.preflop_strategy = PreflopStrategy()
        self.postflop_strategy = PostflopStrategy()
        
        # Anti-Detection
        if self.config.use_anti_detection:
            self.anti_detection = AntiDetectionSystem(
                mistake_probability=self.config.mistake_probability,
                variance_factor=self.config.timing_variance
            )
        else:
            self.anti_detection = None
        
        # Session stats
        self.hands_played = 0
        self.total_profit = 0.0
        
        log.info(f"PokerBot V4.0 initialized")
        log.info(f"Config: {self.config}")
    
    def decide(self, state: GameState) -> Tuple[PokerAction, float]:
        """
        Verilen oyun durumu için karar verir.
        Returns: (action, think_time)
        """
        self.hands_played += 1
        
        log.info(f"=== Hand #{self.hands_played} ===")
        log.info(f"Hero: {state.hero_hand} @ {state.hero_position.name}")
        log.info(f"Board: {state.board}")
        log.info(f"Pot: ${state.pot:.2f} | Stack: ${state.hero_stack:.2f}")
        log.info(f"Facing: ${state.current_bet:.2f}")
        
        # Strateji seçimi
        if state.street == Street.PREFLOP:
            action = self.preflop_strategy.decide(state)
        else:
            action = self.postflop_strategy.decide(state)
        
        log.info(f"Decision: {action}")
        
        # Anti-detection işleme
        think_time = 0.5
        if self.anti_detection:
            # Zor karar mı?
            is_difficult = self._is_difficult_spot(state, action)
            action, think_time = self.anti_detection.process_action(
                action, state.street, state.pot, is_difficult
            )
            log.info(f"Think time: {think_time:.2f}s")
        
        return action, think_time
    
    def _is_difficult_spot(self, state: GameState, action: PokerAction) -> bool:
        """Zor bir karar noktası mı?"""
        # All-in kararı
        if action.action == ActionType.ALL_IN:
            return True
        
        # Büyük bet'e karşı
        if state.current_bet > state.pot * 0.75:
            return True
        
        # River kararları
        if state.street == Street.RIVER:
            return True
        
        return False
    
    def update_result(self, won: bool, profit: float, bad_beat: bool = False):
        """El sonucunu güncelle."""
        self.total_profit += profit
        
        if self.anti_detection:
            self.anti_detection.update_mental_state(
                lost_pot=not won,
                bad_beat=bad_beat
            )
        
        log.info(f"Result: {'WON' if won else 'LOST'} ${abs(profit):.2f}")
        log.info(f"Session P/L: ${self.total_profit:.2f}")
    
    def get_stats(self) -> dict:
        """Bot istatistikleri."""
        stats = {
            "hands_played": self.hands_played,
            "total_profit": self.total_profit,
            "bb_per_100": (self.total_profit / self.config.big_blind) / max(1, self.hands_played) * 100
        }
        
        if self.anti_detection:
            stats["anti_detection"] = self.anti_detection.get_stats()
        
        return stats


class GameController:
    """
    Oyun simülasyonu kontrolcüsü.
    Test ve debugging için kullanılır.
    """
    
    def __init__(self, bot: PokerBot):
        self.bot = bot
        self.action_log: List[PokerAction] = []
    
    def run_hand(
        self,
        hero_hand: List[str],
        board_sequence: List[List[str]],
        villain_actions: List[Tuple[ActionType, float]],
        pot_sequence: List[float],
        hero_position: Position = Position.BTN,
        hero_stack: float = 100.0,
        villain_stack: float = 100.0
    ):
        """
        Tek bir eli simüle eder.
        """
        log.info("\n" + "="*50)
        log.info("STARTING NEW HAND SIMULATION")
        log.info("="*50)
        
        streets = [Street.PREFLOP, Street.FLOP, Street.TURN, Street.RIVER]
        self.action_log = []
        
        current_stack = hero_stack
        hole_cards = HoleCards.from_strings(hero_hand)
        
        for i, (board_cards, (v_action, v_amount), pot) in enumerate(
            zip(board_sequence, villain_actions, pot_sequence)
        ):
            if i >= len(streets):
                break
            
            street = streets[i]
            board = Board.from_strings(board_cards) if board_cards else Board()
            
            log.info(f"\n--- {street.name} ---")
            log.info(f"Board: {board if board.cards else 'None'}")
            log.info(f"Villain: {v_action.name} ${v_amount:.2f}")
            
            # Game state oluştur
            state = GameState(
                street=street,
                hero_hand=hole_cards,
                board=board,
                hero_position=hero_position,
                hero_stack=current_stack,
                villain_stack=villain_stack,
                pot=pot,
                current_bet=v_amount,
                small_blind=0.5,
                big_blind=1.0
            )
            
            # Karar al
            action, think_time = self.bot.decide(state)
            self.action_log.append(action)
            
            log.info(f"HERO: {action}")
            
            # Fold kontrolü
            if action.action == ActionType.FOLD:
                log.info("Hero folded. Hand over.")
                break
            
            # Stack güncelle
            if action.action in [ActionType.CALL, ActionType.BET, ActionType.RAISE]:
                current_stack -= action.amount
        
        log.info("\n" + "="*50)
        log.info("HAND COMPLETE")
        log.info(f"Actions: {[str(a) for a in self.action_log]}")
        log.info("="*50)
        
        return self.action_log
