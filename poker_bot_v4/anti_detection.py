"""
POKER BOT V4.0 - ANTI-DETECTION
===============================
İnsan benzeri davranış simülasyonu.
"""

import time
import random
import math
import logging
from typing import Optional, Tuple
from dataclasses import dataclass

from constants import Street, ActionType, MistakeType

log = logging.getLogger("AntiDetection")


@dataclass
class TimingConfig:
    """Zamanlama ayarları."""
    min_delay: float = 0.5
    max_delay: float = 15.0
    base_think_time: float = 1.5
    difficult_multiplier: float = 2.5
    tilt_fast_factor: float = 0.3
    tilt_slow_factor: float = 2.0


class HumanTimer:
    """İnsan benzeri zamanlama simülatörü."""
    
    def __init__(self, config: Optional[TimingConfig] = None):
        self.config = config or TimingConfig()
        self.tilt_level = 0.0
        self.session_start = time.time()
        self.recent_losses = 0
    
    def get_think_time(
        self, 
        street: Street,
        is_difficult: bool = False,
        action_type: Optional[ActionType] = None
    ) -> float:
        """Log-normal dağılım ile insansı bekleme süresi."""
        mu = self.config.base_think_time
        sigma = 0.5
        
        # Sokak bazlı ayarlama
        street_multipliers = {
            Street.PREFLOP: 0.6,
            Street.FLOP: 1.0,
            Street.TURN: 1.2,
            Street.RIVER: 1.5
        }
        mu *= street_multipliers.get(street, 1.0)
        
        if is_difficult:
            mu *= self.config.difficult_multiplier
            sigma *= 1.5
        
        if action_type:
            if action_type == ActionType.FOLD:
                mu *= 0.5
            elif action_type == ActionType.ALL_IN:
                mu *= 2.0
                sigma *= 1.3
        
        # Tilt etkisi
        if self.tilt_level > 0.5:
            if random.random() < 0.5:
                mu *= self.config.tilt_fast_factor
            else:
                mu *= self.config.tilt_slow_factor
        
        delay = random.lognormvariate(math.log(mu), sigma)
        delay = max(self.config.min_delay, min(delay, self.config.max_delay))
        
        return round(delay, 2)
    
    def update_tilt(self, lost_pot: bool = False, bad_beat: bool = False):
        """Tilt seviyesini güncelle."""
        if bad_beat:
            self.tilt_level = min(1.0, self.tilt_level + 0.3)
        elif lost_pot:
            self.tilt_level = min(1.0, self.tilt_level + 0.1)
        else:
            self.tilt_level = max(0.0, self.tilt_level - 0.05)


class MistakeMaker:
    """Kasıtlı hata yapıcı."""
    
    def __init__(self, mistake_probability: float = 0.03):
        self.mistake_prob = mistake_probability
        self.mistakes_made = 0
        self.total_decisions = 0
    
    def should_make_mistake(self) -> bool:
        """Bu karar için hata yapılmalı mı?"""
        self.total_decisions += 1
        
        if random.random() < self.mistake_prob:
            return True
        
        if self.total_decisions - self.mistakes_made > 100:
            return random.random() < 0.1
        
        return False
    
    def get_mistake_type(self) -> MistakeType:
        """Yapılacak hata tipini seç."""
        self.mistakes_made += 1
        
        weights = {
            MistakeType.OVERBET_BLUFF: 0.20,
            MistakeType.UNDERBET_VALUE: 0.25,
            MistakeType.SLOW_FOLD: 0.15,
            MistakeType.HERO_CALL: 0.25,
            MistakeType.MISSED_VALUE: 0.15
        }
        
        choices = list(weights.keys())
        probs = list(weights.values())
        return random.choices(choices, weights=probs)[0]
    
    def apply_mistake(
        self, 
        original_action: 'PokerAction',
        pot: float,
        mistake_type: MistakeType
    ) -> 'PokerAction':
        """Orijinal aksiyona hata uygular."""
        from data_classes import PokerAction
        
        if mistake_type == MistakeType.OVERBET_BLUFF:
            if original_action.action in [ActionType.BET, ActionType.RAISE]:
                new_amount = original_action.amount * random.uniform(1.5, 2.0)
                return PokerAction(
                    original_action.action, 
                    new_amount,
                    original_action.description + " [MISTAKE:OVERBET]"
                )
        
        elif mistake_type == MistakeType.UNDERBET_VALUE:
            if original_action.action in [ActionType.BET, ActionType.RAISE]:
                new_amount = original_action.amount * random.uniform(0.5, 0.7)
                return PokerAction(
                    original_action.action,
                    max(new_amount, pot * 0.2),
                    original_action.description + " [MISTAKE:UNDERBET]"
                )
        
        elif mistake_type == MistakeType.SLOW_FOLD:
            return PokerAction(
                ActionType.FOLD,
                0,
                original_action.description + " [MISTAKE:SLOW_FOLD]"
            )
        
        elif mistake_type == MistakeType.HERO_CALL:
            if original_action.action == ActionType.FOLD:
                return PokerAction(
                    ActionType.CALL,
                    pot * 0.5,
                    "Hero Call [MISTAKE]"
                )
        
        elif mistake_type == MistakeType.MISSED_VALUE:
            if original_action.action == ActionType.BET:
                return PokerAction(
                    ActionType.CHECK,
                    0,
                    "Missed Value [MISTAKE]"
                )
        
        return original_action
    
    def get_stats(self) -> dict:
        return {
            "total_decisions": self.total_decisions,
            "mistakes_made": self.mistakes_made,
            "mistake_rate": self.mistakes_made / max(1, self.total_decisions)
        }


class BettingPatternVariator:
    """Betting pattern'leri çeşitlendirici."""
    
    def __init__(self, variance_factor: float = 0.15):
        self.variance = variance_factor
        self.history = []
    
    def vary_bet_size(self, base_amount: float, pot: float) -> float:
        """Bet miktarına rastgele varyans ekler."""
        multiplier = random.uniform(1 - self.variance, 1 + self.variance)
        varied = base_amount * multiplier
        varied = self._round_to_human(varied)
        return max(varied, pot * 0.2)
    
    def _round_to_human(self, amount: float) -> float:
        """İnsanların tercih ettiği sayılara yuvarla."""
        if amount < 10:
            return round(amount * 2) / 2
        elif amount < 50:
            return round(amount)
        elif amount < 200:
            return round(amount / 5) * 5
        else:
            return round(amount / 10) * 10
    
    def track_bet(self, amount: float, situation: str):
        """Bet'i kaydet."""
        self.history.append({
            "amount": amount,
            "situation": situation,
            "timestamp": time.time()
        })
        if len(self.history) > 100:
            self.history.pop(0)


class AntiDetectionSystem:
    """Tüm anti-detection bileşenlerini birleştiren ana sistem."""
    
    def __init__(
        self,
        timing_config: Optional[TimingConfig] = None,
        mistake_probability: float = 0.03,
        variance_factor: float = 0.15
    ):
        self.timer = HumanTimer(timing_config)
        self.mistake_maker = MistakeMaker(mistake_probability)
        self.bet_variator = BettingPatternVariator(variance_factor)
        self.enabled = True
        log.info("Anti-Detection System initialized")
    
    def process_action(
        self,
        action: 'PokerAction',
        street: Street,
        pot: float,
        is_difficult: bool = False
    ) -> Tuple['PokerAction', float]:
        """Aksiyonu işler ve anti-detection uygular."""
        if not self.enabled:
            return action, 0.1
        
        think_time = self.timer.get_think_time(
            street, 
            is_difficult,
            action.action
        )
        
        final_action = action
        if self.mistake_maker.should_make_mistake():
            mistake_type = self.mistake_maker.get_mistake_type()
            final_action = self.mistake_maker.apply_mistake(action, pot, mistake_type)
            log.debug(f"Mistake applied: {mistake_type.name}")
        
        if final_action.action in [ActionType.BET, ActionType.RAISE]:
            varied_amount = self.bet_variator.vary_bet_size(final_action.amount, pot)
            final_action.amount = varied_amount
            self.bet_variator.track_bet(varied_amount, f"{street.name}_{final_action.action.name}")
        
        return final_action, think_time
    
    def update_mental_state(self, lost_pot: bool = False, bad_beat: bool = False):
        """Mental durumu güncelle."""
        self.timer.update_tilt(lost_pot, bad_beat)
    
    def get_stats(self) -> dict:
        """Sistem istatistikleri."""
        return {
            "tilt_level": self.timer.tilt_level,
            "mistakes": self.mistake_maker.get_stats(),
            "session_duration": time.time() - self.timer.session_start
        }
