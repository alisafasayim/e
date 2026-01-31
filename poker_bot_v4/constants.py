"""
POKER BOT V4.0 - CONSTANTS & ENUMS
==================================
Tüm sabitler ve enum tanımları.
"""

from enum import Enum, auto
from typing import Dict, List, Tuple

# --- ENUMS ---

class Position(Enum):
    """Masa pozisyonları (6-max)"""
    UTG = 0  # Under The Gun
    MP = 1   # Middle Position  
    CO = 2   # Cutoff
    BTN = 3  # Button
    SB = 4   # Small Blind
    BB = 5   # Big Blind
    
    @property
    def is_early(self) -> bool:
        return self in [Position.UTG, Position.MP]
    
    @property
    def is_late(self) -> bool:
        return self in [Position.CO, Position.BTN]
    
    @property
    def is_blind(self) -> bool:
        return self in [Position.SB, Position.BB]

class Street(Enum):
    PREFLOP = auto()
    FLOP = auto()
    TURN = auto()
    RIVER = auto()

class ActionType(Enum):
    FOLD = "FOLD"
    CHECK = "CHECK"
    CALL = "CALL"
    BET = "BET"
    RAISE = "RAISE"
    ALL_IN = "ALL_IN"

class BoardTexture(Enum):
    """Board dokusu kategorileri"""
    UNKNOWN = 0
    DRY_RAINBOW = 1       # K72 rainbow - çok kuru
    DRY_TWOTONE = 2       # K72 iki renk
    SEMI_WET = 3          # 982 iki renk, biraz bağlantı
    WET_FLUSHY = 4        # Aynı renkten 2+ kart
    WET_STRAIGHTY = 5     # Bağlantılı (789, JT9)
    VERY_WET = 6          # Monotone veya çok bağlantılı
    PAIRED = 7            # Board'da pair var (KK2, 877)
    TRIPS_BOARD = 8       # Board'da trips var (KKK)

class HandCategory(Enum):
    """El kategorileri (Made hands)"""
    HIGH_CARD = 1
    PAIR = 2
    TWO_PAIR = 3
    THREE_OF_A_KIND = 4
    STRAIGHT = 5
    FLUSH = 6
    FULL_HOUSE = 7
    FOUR_OF_A_KIND = 8
    STRAIGHT_FLUSH = 9
    ROYAL_FLUSH = 10

class DrawType(Enum):
    """Draw türleri"""
    NONE = 0
    GUTSHOT = 1           # 4 out straight draw
    OESD = 2              # 8 out open-ended straight draw
    FLUSH_DRAW = 3        # 9 out flush draw
    COMBO_DRAW = 4        # Flush + Straight draw (12+ out)
    BACKDOOR_FLUSH = 5    # Runner-runner flush
    BACKDOOR_STRAIGHT = 6 # Runner-runner straight

# --- CARD CONSTANTS ---

RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']
SUITS = ['c', 'd', 'h', 's']  # clubs, diamonds, hearts, spades

RANK_VALUES: Dict[str, int] = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
    '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 14
}

# Ace-low straight için alternatif değer
RANK_VALUES_LOW_ACE: Dict[str, int] = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8,
    '9': 9, 'T': 10, 'J': 11, 'Q': 12, 'K': 13, 'A': 1
}

# --- GAME CONSTANTS ---
SMALL_BLIND = 1
BIG_BLIND = 2
MAX_PLAYERS = 6

# --- MONTE CARLO SETTINGS ---
MONTE_CARLO_ITERATIONS = 1000  # Simülasyon sayısı (performans/doğruluk dengesi)
SIMULATION_TIMEOUT = 2.0       # Maksimum hesaplama süresi (saniye)

# --- STRATEGY CONSTANTS ---

# SPR (Stack-to-Pot Ratio) Eşikleri
SPR_SHALLOW = 4.0      # Shallow stack play
SPR_MEDIUM = 10.0      # Normal play
SPR_DEEP = 20.0        # Deep stack play

# Pot Odds Marjı
POT_ODDS_MARGIN = 0.05  # %5 marj (implied odds için)

# Equity Eşikleri
MIN_EQUITY_TO_BLUFF = 0.35     # Semi-bluff için minimum equity
VALUE_BET_THRESHOLD = 0.65     # Value bet için gereken equity
FOLD_TO_3BET_THRESHOLD = 0.40  # 3-Bet'e fold üst sınırı

# Bluff Frekansları (MDF - Minimum Defense Frequency bazlı)
BLUFF_FREQ_DRY = 0.25   # Kuru boardlarda daha az bluff
BLUFF_FREQ_WET = 0.15   # Islak boardlarda daha az bluff (çekilir)

# Bet Sizing Standartları (pot yüzdesi)
BET_SIZE_SMALL = 0.33   # 1/3 pot
BET_SIZE_MEDIUM = 0.50  # 1/2 pot
BET_SIZE_LARGE = 0.75   # 3/4 pot
BET_SIZE_OVERBET = 1.25 # Overbet

# --- MISTAKE TYPES (Anti-Detection) ---

class MistakeType(Enum):
    """Kasıtlı hata türleri (insan gibi görünmek için)"""
    OVERBET_BLUFF = 1     # Bluff'ta çok büyük bet
    UNDERBET_VALUE = 2    # Value'da küçük bet
    SLOW_FOLD = 3         # Kolay fold'da geç kalmak
    HERO_CALL = 4         # Gereksiz hero call
    MISSED_VALUE = 5      # Value bet kaçırmak
