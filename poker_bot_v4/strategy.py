"""
POKER BOT V4.0 - STRATEGY ENGINE
================================
GTO ve Exploitative strateji karışımı.
"""

import random
import math
import logging
from typing import Tuple, Optional, List

from constants import (
    Position, Street, ActionType, BoardTexture,
    SPR_SHALLOW, SPR_MEDIUM, SPR_DEEP,
    POT_ODDS_MARGIN, BLUFF_FREQ_DRY, BLUFF_FREQ_WET,
    BET_SIZE_SMALL, BET_SIZE_MEDIUM, BET_SIZE_LARGE, BET_SIZE_OVERBET
)
from data_classes import (
    HoleCards, Board, GameState, PokerAction, HandStrength, 
    BoardAnalysis, PlayerStats
)
from hand_evaluator import HandEvaluator, BoardAnalyzer
from preflop_ranges import (
    hand_to_notation, is_hand_in_range,
    get_rfi_range, get_3bet_range, get_bb_defense_range
)

log = logging.getLogger("Strategy")


class BetSizer:
    """Dinamik bet sizing hesaplayıcı."""
    
    @staticmethod
    def calculate_value_bet(
        pot: float,
        hand: HandStrength,
        board: BoardAnalysis,
        spr: float,
        villain_type: Optional[str] = None
    ) -> float:
        """
        Value bet için optimal sizing.
        """
        base_size = pot * BET_SIZE_MEDIUM  # Başlangıç: %50 pot
        
        # SPR ayarlaması
        if spr < SPR_SHALLOW:
            # Shallow stack - pot commit için büyük
            base_size = pot * BET_SIZE_LARGE
        elif spr > SPR_DEEP:
            # Deep stack - daha küçük, pot kontrolü
            base_size = pot * BET_SIZE_SMALL
        
        # Board texture ayarlaması
        if board.danger_level >= 7:
            # Çok tehlikeli board - büyük bet ile protect
            base_size *= 1.3
        elif board.danger_level <= 3:
            # Kuru board - küçük bet, rakibi çağırmaya teşvik
            base_size *= 0.8
        
        # Rakip tipine göre ayarlama
        if villain_type:
            if villain_type == "FISH":
                # Calling station - max value
                base_size *= 1.2
            elif villain_type == "NIT":
                # Çok tight - küçük bet, bluff yakalama şansı düşük
                base_size *= 0.7
            elif villain_type == "LAG":
                # Agresif - trap için küçük
                base_size *= 0.6
        
        # Nut advantage
        if hand.is_nut:
            # Overbet potansiyeli
            if random.random() < 0.3:  # %30 ihtimalle overbet
                base_size = pot * BET_SIZE_OVERBET
        
        return round(max(base_size, pot * 0.25), 2)  # Min %25 pot
    
    @staticmethod
    def calculate_bluff_bet(
        pot: float,
        board: BoardAnalysis,
        has_blockers: bool = False
    ) -> float:
        """
        Bluff bet sizing.
        Genel kural: Kuru board'da küçük, ıslak board'da 0 veya büyük.
        """
        # Islak board'da bluff riski yüksek
        if board.danger_level >= 6:
            # Ya bluff yapma ya da büyük yap
            if random.random() < 0.3:  # %30 ihtimalle büyük bluff
                return round(pot * BET_SIZE_LARGE, 2)
            return 0.0
        
        # Kuru board - küçük bluff etkili
        base_size = pot * BET_SIZE_SMALL
        
        # Blocker varsa daha büyük
        if has_blockers:
            base_size *= 1.2
        
        return round(base_size, 2)
    
    @staticmethod
    def calculate_raise_size(
        pot: float,
        facing_bet: float,
        is_value: bool,
        spr: float
    ) -> float:
        """
        Raise sizing hesaplar.
        """
        # Minimum raise
        min_raise = facing_bet * 2
        
        # Pot-sized raise
        pot_raise = pot + facing_bet * 2
        
        if is_value:
            # Value raise - pot-sized veya biraz üstü
            if spr < SPR_SHALLOW:
                return pot_raise * 1.2  # All-in'e yakın
            return min(pot_raise, pot_raise * random.uniform(0.9, 1.1))
        else:
            # Bluff raise - daha küçük (fold equity/risk oranı)
            return min(min_raise * 2.5, pot_raise * 0.7)


class PreflopStrategy:
    """Preflop karar motoru."""
    
    def __init__(self):
        pass
    
    def decide(self, state: GameState) -> PokerAction:
        """
        Preflop aksiyonu belirler.
        """
        hand = state.hero_hand
        position = state.hero_position
        current_bet = state.current_bet
        stack = state.hero_stack
        bb = state.big_blind
        
        # Hand notation
        notation = hand_to_notation(
            hand.card1.rank, 
            hand.card2.rank,
            hand.is_suited
        )
        
        log.debug(f"Preflop: {notation} from {position.name}, facing ${current_bet}")
        
        # --- SCENARIO: İlk açış (RFI) ---
        if current_bet <= bb:
            rfi_range = get_rfi_range(position)
            
            if is_hand_in_range(notation, rfi_range):
                raise_size = self._get_open_raise_size(position, bb)
                return PokerAction(
                    ActionType.RAISE, 
                    min(raise_size, stack),
                    f"RFI {notation}"
                )
            
            # Limp (genelde iyi değil ama SB'de kabul edilebilir)
            if position == Position.SB and self._should_limp(notation):
                return PokerAction(ActionType.CALL, bb / 2, "SB Limp")
            
            return PokerAction(ActionType.FOLD, 0, "Not in range")
        
        # --- SCENARIO: Raise'e karşı (Facing Raise) ---
        raiser_position = state.villain_position  # Basitleştirilmiş
        
        # 3-bet range kontrolü
        three_bet_range = get_3bet_range(raiser_position)
        if is_hand_in_range(notation, three_bet_range):
            three_bet_size = current_bet * 3
            if position in [Position.SB, Position.BB]:
                three_bet_size = current_bet * 3.5  # OOP'da daha büyük
            return PokerAction(
                ActionType.RAISE,
                min(three_bet_size, stack),
                f"3-bet {notation} vs {raiser_position.name}"
            )
        
        # BB defense
        if position == Position.BB:
            defense_range = get_bb_defense_range(raiser_position)
            if is_hand_in_range(notation, defense_range):
                return PokerAction(
                    ActionType.CALL,
                    current_bet - state.hero_invested,
                    f"BB Defense {notation}"
                )
        
        # Cold call (CO/BTN)
        if position in [Position.CO, Position.BTN]:
            if self._should_cold_call(notation, raiser_position):
                return PokerAction(
                    ActionType.CALL,
                    current_bet - state.hero_invested,
                    f"Cold Call {notation}"
                )
        
        return PokerAction(ActionType.FOLD, 0, "Not defending")
    
    def _get_open_raise_size(self, position: Position, bb: float) -> float:
        """Pozisyona göre açış büyüklüğü."""
        # Modern GTO: 2-2.5x açış
        if position.is_early:
            return bb * 2.5
        elif position.is_late:
            return bb * 2.2
        else:  # Blinds
            return bb * 3  # SB'den daha büyük
    
    def _should_limp(self, notation: str) -> bool:
        """SB'den limp edilecek eller."""
        limp_hands = {"22", "33", "44", "55", "66", "76s", "65s", "54s", "K2s", "K3s", "Q2s"}
        return notation in limp_hands
    
    def _should_cold_call(self, notation: str, vs_position: Position) -> bool:
        """Cold call edilecek eller (set mining, implied odds)."""
        # Küçük pair'ler set mining için
        if notation in ["22", "33", "44", "55", "66", "77"]:
            return True
        # Suited connectors
        if notation in ["98s", "87s", "76s", "65s", "54s"]:
            return True
        return False


class PostflopStrategy:
    """Postflop karar motoru."""
    
    def __init__(self):
        self.evaluator = HandEvaluator()
        self.board_analyzer = BoardAnalyzer()
        self.bet_sizer = BetSizer()
    
    def decide(self, state: GameState) -> PokerAction:
        """
        Postflop aksiyonu belirler.
        """
        # Analizler
        hand_strength = self.evaluator.evaluate_hand(state.hero_hand, state.board)
        board_analysis = self.board_analyzer.analyze(state.board)
        
        log.debug(f"Street: {state.street.name}")
        log.debug(f"Hand: {hand_strength.made_hand_desc} (Equity: {hand_strength.equity:.2f})")
        log.debug(f"Board: {board_analysis.description} (Danger: {board_analysis.danger_level})")
        
        villain_type = state.villain_stats.player_type if state.villain_stats else None
        
        # --- FACING BET ---
        if state.current_bet > 0:
            return self._decide_facing_bet(state, hand_strength, board_analysis, villain_type)
        
        # --- CHECKED TO US ---
        return self._decide_checked_to(state, hand_strength, board_analysis, villain_type)
    
    def _decide_facing_bet(
        self, 
        state: GameState,
        hand: HandStrength,
        board: BoardAnalysis,
        villain_type: Optional[str]
    ) -> PokerAction:
        """Rakip bet yaptığında karar."""
        
        pot = state.pot
        facing_bet = state.get_call_amount()
        pot_odds = state.pot_odds
        equity = hand.equity
        spr = state.spr
        
        log.debug(f"Facing ${facing_bet} into ${pot} (Pot Odds: {pot_odds:.2f})")
        
        # === VERY STRONG HAND (Raise for Value) ===
        if equity >= 0.80:
            # Raise mı yoksa trap mı?
            should_raise = self._should_raise_for_value(hand, board, spr, villain_type)
            
            if should_raise:
                raise_size = self.bet_sizer.calculate_raise_size(
                    pot, facing_bet, is_value=True, spr=spr
                )
                if raise_size >= state.hero_stack * 0.9:
                    return PokerAction(ActionType.ALL_IN, state.hero_stack, "All-in Value")
                return PokerAction(ActionType.RAISE, raise_size, "Value Raise")
            
            # Trap call
            return PokerAction(ActionType.CALL, facing_bet, "Trap Call")
        
        # === GOOD HAND (Call or Fold) ===
        if equity >= 0.50:
            # Pot odds check
            if equity > pot_odds + POT_ODDS_MARGIN:
                return PokerAction(ActionType.CALL, facing_bet, "Profitable Call")
            
            # Implied odds ile call
            if self._has_implied_odds(hand, spr, villain_type):
                return PokerAction(ActionType.CALL, facing_bet, "Implied Odds Call")
            
            return PokerAction(ActionType.FOLD, 0, "Marginal Fold")
        
        # === DRAWING HAND ===
        if hand.has_draw and hand.draw_outs >= 8:
            # Draw equity hesabı
            draw_equity = hand.draw_outs * (0.02 if state.street == Street.RIVER else 0.04)
            
            # Semi-bluff raise
            if self._should_semi_bluff(hand, board, spr):
                raise_size = self.bet_sizer.calculate_raise_size(
                    pot, facing_bet, is_value=False, spr=spr
                )
                return PokerAction(ActionType.RAISE, raise_size, "Semi-bluff Raise")
            
            # Call with correct odds
            if draw_equity > pot_odds:
                return PokerAction(ActionType.CALL, facing_bet, "Drawing Call")
        
        # === WEAK HAND ===
        # Hero call consideration
        if self._should_hero_call(hand, board, villain_type, facing_bet, pot):
            return PokerAction(ActionType.CALL, facing_bet, "Hero Call")
        
        return PokerAction(ActionType.FOLD, 0, "Low Equity Fold")
    
    def _decide_checked_to(
        self,
        state: GameState,
        hand: HandStrength,
        board: BoardAnalysis,
        villain_type: Optional[str]
    ) -> PokerAction:
        """Önümüz boşken karar."""
        
        pot = state.pot
        spr = state.spr
        equity = hand.equity
        
        # === VALUE BET ===
        if equity >= 0.65:
            bet_size = self.bet_sizer.calculate_value_bet(
                pot, hand, board, spr, villain_type
            )
            
            if bet_size >= state.hero_stack * 0.9:
                return PokerAction(ActionType.ALL_IN, state.hero_stack, "All-in Value")
            
            return PokerAction(ActionType.BET, bet_size, "Value Bet")
        
        # === C-BET (Continuation Bet) ===
        if state.street == Street.FLOP and self._should_cbet(hand, board, villain_type):
            cbet_size = self._calculate_cbet_size(pot, board)
            return PokerAction(ActionType.BET, cbet_size, "C-bet")
        
        # === SEMI-BLUFF with Draw ===
        if hand.has_draw and hand.draw_outs >= 8:
            if self._should_semi_bluff_bet(hand, board, spr):
                bet_size = pot * BET_SIZE_MEDIUM
                return PokerAction(ActionType.BET, bet_size, "Semi-bluff Bet")
        
        # === PURE BLUFF ===
        bluff_freq = BLUFF_FREQ_DRY if board.danger_level <= 4 else BLUFF_FREQ_WET
        if random.random() < bluff_freq:
            # Bluff spot kontrolü
            if self._is_good_bluff_spot(board, villain_type):
                bluff_size = self.bet_sizer.calculate_bluff_bet(
                    pot, board, has_blockers=bool(hand.blockers)
                )
                if bluff_size > 0:
                    return PokerAction(ActionType.BET, bluff_size, "Bluff Bet")
        
        return PokerAction(ActionType.CHECK, 0, "Check Back")
    
    # --- HELPER METHODS ---
    
    def _should_raise_for_value(
        self, hand: HandStrength, board: BoardAnalysis, 
        spr: float, villain_type: Optional[str]
    ) -> bool:
        """Value raise mı yapmalı?"""
        # Islak board'da protect için raise
        if board.danger_level >= 6:
            return True
        
        # Nut hand - bazen trap
        if hand.is_nut:
            return random.random() > 0.35  # %65 raise
        
        # Calling station'a karşı raise
        if villain_type == "FISH":
            return True
        
        # Agresif oyuncuya karşı trap
        if villain_type == "LAG":
            return random.random() > 0.5  # %50 trap
        
        return True  # Default raise
    
    def _has_implied_odds(
        self, hand: HandStrength, spr: float, villain_type: Optional[str]
    ) -> bool:
        """Implied odds var mı?"""
        # Deep stack + Draw
        if spr > SPR_MEDIUM and hand.has_draw:
            return True
        
        # Calling station (para verir)
        if villain_type == "FISH":
            return True
        
        return False
    
    def _should_semi_bluff(
        self, hand: HandStrength, board: BoardAnalysis, spr: float
    ) -> bool:
        """Semi-bluff raise yapmalı mı?"""
        # Güçlü draw (12+ out)
        if hand.draw_outs >= 12:
            return random.random() < 0.6  # %60
        
        # Normal draw + fold equity
        if hand.draw_outs >= 8 and spr > SPR_SHALLOW:
            return random.random() < 0.35  # %35
        
        return False
    
    def _should_hero_call(
        self, hand: HandStrength, board: BoardAnalysis,
        villain_type: Optional[str], bet: float, pot: float
    ) -> bool:
        """Hero call yapmalı mı?"""
        # Kuru board + agresif rakip
        if board.danger_level <= 3 and villain_type in ["LAG", None]:
            if hand.equity > 0.35:
                return random.random() < 0.15  # %15 hero call
        
        # Küçük bet (probe/blocker bet)
        if bet < pot * 0.4 and hand.equity > 0.30:
            return random.random() < 0.25  # %25
        
        return False
    
    def _should_cbet(
        self, hand: HandStrength, board: BoardAnalysis,
        villain_type: Optional[str]
    ) -> bool:
        """C-bet yapmalı mı?"""
        # Güçlü el - her zaman
        if hand.equity >= 0.50:
            return True
        
        # Kuru board - yüksek c-bet frequency
        if board.danger_level <= 4:
            return random.random() < 0.70  # %70
        
        # Islak board - sadece value veya iyi draw
        if board.danger_level >= 6:
            return hand.equity >= 0.45 or hand.draw_outs >= 8
        
        # Orta board
        return random.random() < 0.50  # %50
    
    def _calculate_cbet_size(self, pot: float, board: BoardAnalysis) -> float:
        """C-bet size hesaplar."""
        if board.danger_level >= 6:
            # Islak board - büyük c-bet
            return round(pot * BET_SIZE_LARGE, 2)
        elif board.danger_level <= 3:
            # Kuru board - küçük c-bet
            return round(pot * BET_SIZE_SMALL, 2)
        else:
            return round(pot * BET_SIZE_MEDIUM, 2)
    
    def _should_semi_bluff_bet(
        self, hand: HandStrength, board: BoardAnalysis, spr: float
    ) -> bool:
        """Semi-bluff bet yapmalı mı?"""
        # Fold equity gerekli
        if spr < SPR_SHALLOW:
            return False  # Stack çok kısa, fold ettirmek zor
        
        # İyi draw
        if hand.draw_outs >= 12:
            return random.random() < 0.70
        elif hand.draw_outs >= 8:
            return random.random() < 0.45
        
        return False
    
    def _is_good_bluff_spot(
        self, board: BoardAnalysis, villain_type: Optional[str]
    ) -> bool:
        """İyi bluff spot'u mu?"""
        # Calling station'a bluff yapma
        if villain_type == "FISH":
            return False
        
        # Çok ıslak board - bluff tehlikeli
        if board.danger_level >= 7:
            return False
        
        # Kuru board - iyi spot
        if board.danger_level <= 4:
            return True
        
        return random.random() < 0.40
