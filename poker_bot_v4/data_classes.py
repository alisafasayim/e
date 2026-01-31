"""
POKER BOT V4.0 - DATA CLASSES
=============================
Oyun durumu ve el değerlendirmesi için veri yapıları.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set, Tuple, Any
from constants import (
    Position, Street, ActionType, BoardTexture, 
    HandCategory, DrawType
)

@dataclass
class Card:
    """Tek bir kartı temsil eder."""
    rank: str  # '2'-'9', 'T', 'J', 'Q', 'K', 'A'
    suit: str  # 'c', 'd', 'h', 's'
    
    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"
    
    def __repr__(self) -> str:
        return self.__str__()
    
    @classmethod
    def from_string(cls, card_str: str) -> 'Card':
        """'Ah', 'Kc' gibi string'den Card oluşturur."""
        if len(card_str) != 2:
            raise ValueError(f"Geçersiz kart formatı: {card_str}")
        return cls(rank=card_str[0].upper(), suit=card_str[1].lower())
    
    @property
    def value(self) -> int:
        from constants import RANK_VALUES
        return RANK_VALUES.get(self.rank, 0)

@dataclass
class HoleCards:
    """Oyuncunun elindeki 2 kart."""
    card1: Card
    card2: Card
    
    def __str__(self) -> str:
        return f"{self.card1}{self.card2}"
    
    @property
    def is_pocket_pair(self) -> bool:
        return self.card1.rank == self.card2.rank
    
    @property
    def is_suited(self) -> bool:
        return self.card1.suit == self.card2.suit
    
    @property
    def is_connected(self) -> bool:
        """Kartlar ardışık mı (örn: JT, 98)?"""
        diff = abs(self.card1.value - self.card2.value)
        return diff == 1
    
    @property
    def gap(self) -> int:
        """Kartlar arasındaki boşluk (örn: J9 -> gap=1)."""
        return abs(self.card1.value - self.card2.value) - 1
    
    @property
    def high_card(self) -> Card:
        return self.card1 if self.card1.value >= self.card2.value else self.card2
    
    @property
    def low_card(self) -> Card:
        return self.card2 if self.card1.value >= self.card2.value else self.card1
    
    @classmethod
    def from_strings(cls, cards: List[str]) -> 'HoleCards':
        """['Ah', 'Kc'] gibi listeden HoleCards oluşturur."""
        if len(cards) != 2:
            raise ValueError(f"El 2 kart içermeli: {cards}")
        return cls(Card.from_string(cards[0]), Card.from_string(cards[1]))

@dataclass 
class Board:
    """Masadaki community kartları."""
    cards: List[Card] = field(default_factory=list)
    
    def __str__(self) -> str:
        return " ".join(str(c) for c in self.cards)
    
    @property
    def street(self) -> Street:
        n = len(self.cards)
        if n == 0:
            return Street.PREFLOP
        elif n == 3:
            return Street.FLOP
        elif n == 4:
            return Street.TURN
        elif n == 5:
            return Street.RIVER
        else:
            raise ValueError(f"Geçersiz board kartı sayısı: {n}")
    
    @classmethod
    def from_strings(cls, cards: List[str]) -> 'Board':
        return cls([Card.from_string(c) for c in cards])
    
    def add_card(self, card: Card) -> None:
        if len(self.cards) >= 5:
            raise ValueError("Board zaten 5 kart içeriyor")
        self.cards.append(card)

@dataclass
class PokerAction:
    """Bir poker aksiyonu."""
    action: ActionType
    amount: float = 0.0
    description: str = ""
    confidence: float = 1.0  # 0-1 arası, kararın güvenilirliği
    
    def __str__(self) -> str:
        if self.amount > 0:
            return f"{self.action.value} ${self.amount:.2f}"
        return self.action.value

@dataclass
class HandStrength:
    """El gücü analizi."""
    # Temel metrikler
    equity: float = 0.0           # 0-1 arası kazanma şansı
    hand_category: HandCategory = HandCategory.HIGH_CARD
    hand_rank: int = 0            # Aynı kategori içinde sıralama
    
    # Made hand bilgisi
    is_made_hand: bool = False
    made_hand_desc: str = ""      # "Top Pair, King Kicker"
    
    # Draw bilgisi
    has_draw: bool = False
    draw_type: DrawType = DrawType.NONE
    draw_outs: int = 0
    draw_equity: float = 0.0      # Draw tamamlanırsa equity
    
    # Özel durumlar
    is_nut: bool = False          # Mümkün en iyi el mi?
    is_second_nut: bool = False
    blockers: List[str] = field(default_factory=list)  # Bloke ettiği eller
    
    # Board interaction
    uses_both_cards: bool = False  # İki kartı da kullanıyor mu?
    vulnerable: bool = False       # Kolay geçilebilir mi?

@dataclass
class BoardAnalysis:
    """Board dokusu analizi."""
    texture: BoardTexture = BoardTexture.UNKNOWN
    
    # Flush analizi
    flush_possible: bool = False
    flush_draw_possible: bool = False
    flush_suit: Optional[str] = None
    same_suit_count: int = 0
    
    # Straight analizi  
    straight_possible: bool = False
    straight_draw_possible: bool = False
    connected_count: int = 0
    
    # Pairing
    is_paired: bool = False
    is_double_paired: bool = False
    is_trips: bool = False
    pair_rank: Optional[str] = None
    
    # High card info
    highest_card: Optional[Card] = None
    broadway_count: int = 0  # T, J, Q, K, A sayısı
    
    # Tehlike seviyesi (0-10)
    danger_level: int = 0
    
    # Açıklama
    description: str = ""

@dataclass
class PlayerStats:
    """Rakip istatistikleri (opponent modeling)."""
    player_id: str = ""
    hands_played: int = 0
    
    # Preflop stats
    vpip: float = 0.0        # Voluntarily Put In Pot
    pfr: float = 0.0         # Preflop Raise
    three_bet: float = 0.0   # 3-bet frequency
    fold_to_3bet: float = 0.0
    
    # Postflop stats
    aggression_factor: float = 0.0  # (Bet+Raise) / Call
    cbet_flop: float = 0.0          # C-bet frequency flop
    cbet_turn: float = 0.0          # C-bet frequency turn
    fold_to_cbet: float = 0.0
    
    # Showdown stats
    wtsd: float = 0.0        # Went To ShowDown
    won_at_sd: float = 0.0   # Won $ at ShowDown
    
    @property
    def is_tight(self) -> bool:
        return self.vpip < 20
    
    @property
    def is_loose(self) -> bool:
        return self.vpip > 30
    
    @property
    def is_passive(self) -> bool:
        return self.aggression_factor < 1.0
    
    @property
    def is_aggressive(self) -> bool:
        return self.aggression_factor > 2.0
    
    @property
    def player_type(self) -> str:
        """TAG, LAG, Nit, Fish gibi oyuncu tipi."""
        if self.is_tight and self.is_aggressive:
            return "TAG"  # Tight-Aggressive
        elif self.is_loose and self.is_aggressive:
            return "LAG"  # Loose-Aggressive
        elif self.is_tight and self.is_passive:
            return "NIT"  # Çok sıkı
        elif self.is_loose and self.is_passive:
            return "FISH" # Calling Station
        else:
            return "REG"  # Regular

@dataclass
class GameState:
    """Oyunun anlık durumu."""
    # Temel bilgiler
    hand_id: str = ""
    street: Street = Street.PREFLOP
    
    # Kartlar
    hero_hand: Optional[HoleCards] = None
    board: Board = field(default_factory=Board)
    
    # Pozisyon
    hero_position: Position = Position.BB
    villain_position: Position = Position.BTN
    
    # Stack ve pot
    hero_stack: float = 100.0
    villain_stack: float = 100.0
    pot: float = 0.0
    
    # Mevcut betting round
    current_bet: float = 0.0      # Mevcut açık bet
    hero_invested: float = 0.0    # Hero'nun bu sokakta yatırdığı
    villain_invested: float = 0.0 # Villain'in bu sokakta yatırdığı
    
    # Betting history
    actions_this_street: List[PokerAction] = field(default_factory=list)
    actions_preflop: List[PokerAction] = field(default_factory=list)
    actions_flop: List[PokerAction] = field(default_factory=list)
    actions_turn: List[PokerAction] = field(default_factory=list)
    actions_river: List[PokerAction] = field(default_factory=list)
    
    # Rakip bilgisi
    villain_stats: Optional[PlayerStats] = None
    
    # Blinds
    small_blind: float = 0.5
    big_blind: float = 1.0
    
    @property
    def effective_stack(self) -> float:
        """Oynanabilir stack (ikisinin minimumu)."""
        return min(self.hero_stack, self.villain_stack)
    
    @property
    def spr(self) -> float:
        """Stack-to-Pot Ratio."""
        if self.pot <= 0:
            return float('inf')
        return self.effective_stack / self.pot
    
    @property
    def pot_odds(self) -> float:
        """Mevcut pot odds (call için)."""
        call_amount = self.current_bet - self.hero_invested
        if call_amount <= 0:
            return 0.0
        total_pot = self.pot + call_amount
        return call_amount / total_pot
    
    @property
    def is_heads_up(self) -> bool:
        return True  # Şimdilik sadece HU destekleniyor
    
    def get_call_amount(self) -> float:
        return max(0, self.current_bet - self.hero_invested)
    
    def get_min_raise(self) -> float:
        """Minimum legal raise miktarı."""
        last_raise = self.current_bet  # Basitleştirilmiş
        return self.current_bet + max(last_raise, self.big_blind)
