"""
POKER BOT V4.0 - PREFLOP RANGES
===============================
Pozisyon bazlı GTO preflop range tabloları.
"""

from typing import Dict, Set, List
from constants import Position

# Hand notasyonu: 
# - "AA", "KK" = Pocket pairs
# - "AKs" = Suited (aynı renk)
# - "AKo" = Offsuit (farklı renk)

# --- OPENING RANGES (RFI - Raise First In) ---

RFI_RANGES: Dict[Position, Set[str]] = {
    
    Position.UTG: {
        # Pairs: 77+
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77",
        # Suited: ATs+, KQs
        "AKs", "AQs", "AJs", "ATs", "KQs",
        # Offsuit: AQo+
        "AKo", "AQo"
    },
    
    Position.MP: {
        # Pairs: 66+
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66",
        # Suited: A9s+, KJs+, QJs
        "AKs", "AQs", "AJs", "ATs", "A9s",
        "KQs", "KJs", "QJs",
        # Offsuit: AJo+, KQo
        "AKo", "AQo", "AJo", "KQo"
    },
    
    Position.CO: {
        # Pairs: 55+
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55",
        # Suited: A2s+, K9s+, Q9s+, J9s+, T9s, 98s, 87s
        "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
        "KQs", "KJs", "KTs", "K9s",
        "QJs", "QTs", "Q9s",
        "JTs", "J9s",
        "T9s", "98s", "87s",
        # Offsuit: ATo+, KJo+, QJo
        "AKo", "AQo", "AJo", "ATo", "KQo", "KJo", "QJo"
    },
    
    Position.BTN: {
        # Pairs: 22+
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44", "33", "22",
        # Suited: Çoğu suited
        "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
        "KQs", "KJs", "KTs", "K9s", "K8s", "K7s", "K6s", "K5s",
        "QJs", "QTs", "Q9s", "Q8s",
        "JTs", "J9s", "J8s",
        "T9s", "T8s",
        "98s", "97s",
        "87s", "86s",
        "76s", "75s",
        "65s", "64s",
        "54s", "53s",
        # Offsuit: A7o+, K9o+, Q9o+, J9o+, T9o
        "AKo", "AQo", "AJo", "ATo", "A9o", "A8o", "A7o",
        "KQo", "KJo", "KTo", "K9o",
        "QJo", "QTo", "Q9o",
        "JTo", "J9o",
        "T9o"
    },
    
    Position.SB: {
        # BTN gibi geniş ama biraz daha dikkatli
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44", "33", "22",
        "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
        "KQs", "KJs", "KTs", "K9s", "K8s", "K7s",
        "QJs", "QTs", "Q9s", "Q8s",
        "JTs", "J9s", "J8s",
        "T9s", "T8s",
        "98s", "97s",
        "87s", "86s",
        "76s", "75s",
        "65s",
        "54s",
        "AKo", "AQo", "AJo", "ATo", "A9o", "A8o", "A7o", "A6o", "A5o",
        "KQo", "KJo", "KTo", "K9o",
        "QJo", "QTo",
        "JTo"
    },
    
    Position.BB: set()  # BB genelde RFI yapmaz, defend eder
}

# --- 3-BET RANGES ---

THREE_BET_VALUE: Dict[Position, Set[str]] = {
    Position.UTG: {"AA", "KK", "QQ", "AKs", "AKo"},
    Position.MP: {"AA", "KK", "QQ", "JJ", "AKs", "AKo"},
    Position.CO: {"AA", "KK", "QQ", "JJ", "TT", "AKs", "AQs", "AKo"},
    Position.BTN: {"AA", "KK", "QQ", "JJ", "TT", "99", "AKs", "AQs", "AJs", "AKo", "AQo"},
    Position.SB: {"AA", "KK", "QQ", "JJ", "TT", "99", "AKs", "AQs", "AJs", "AKo", "AQo"},
    Position.BB: {"AA", "KK", "QQ", "JJ", "TT", "AKs", "AQs", "AKo"}
}

THREE_BET_BLUFF: Dict[Position, Set[str]] = {
    Position.UTG: set(),  # UTG'ye karşı bluff 3-bet tehlikeli
    Position.MP: {"A5s", "A4s"},
    Position.CO: {"A5s", "A4s", "A3s", "76s", "65s"},
    Position.BTN: {"A5s", "A4s", "A3s", "A2s", "K9s", "Q9s", "76s", "65s", "54s"},
    Position.SB: {"A5s", "A4s", "A3s", "A2s", "K9s", "Q9s", "J9s", "76s", "65s", "54s"},
    Position.BB: {"A5s", "A4s", "A3s", "A2s", "K9s", "Q9s", "J9s", "87s", "76s", "65s"}
}

# --- BB DEFENSE RANGES ---

BB_CALL_VS_POSITION: Dict[Position, Set[str]] = {
    # BB'den hangi raiser'a karşı ne call edilir
    Position.UTG: {
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66",
        "AKs", "AQs", "AJs", "ATs", "A9s", "A8s",
        "KQs", "KJs", "KTs",
        "QJs", "QTs",
        "JTs",
        "T9s", "98s",
        "AKo", "AQo", "AJo",
        "KQo"
    },
    Position.MP: {
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55",
        "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s",
        "KQs", "KJs", "KTs", "K9s",
        "QJs", "QTs", "Q9s",
        "JTs", "J9s",
        "T9s", "98s", "87s",
        "AKo", "AQo", "AJo", "ATo",
        "KQo", "KJo"
    },
    Position.CO: {
        # CO'ya karşı daha geniş
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44", "33", "22",
        "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
        "KQs", "KJs", "KTs", "K9s", "K8s", "K7s",
        "QJs", "QTs", "Q9s", "Q8s",
        "JTs", "J9s", "J8s",
        "T9s", "T8s",
        "98s", "97s",
        "87s", "86s",
        "76s", "75s",
        "65s",
        "54s",
        "AKo", "AQo", "AJo", "ATo", "A9o",
        "KQo", "KJo", "KTo",
        "QJo", "QTo",
        "JTo"
    },
    Position.BTN: {
        # BTN'a karşı en geniş defense
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44", "33", "22",
        "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
        "KQs", "KJs", "KTs", "K9s", "K8s", "K7s", "K6s", "K5s", "K4s",
        "QJs", "QTs", "Q9s", "Q8s", "Q7s", "Q6s",
        "JTs", "J9s", "J8s", "J7s",
        "T9s", "T8s", "T7s",
        "98s", "97s", "96s",
        "87s", "86s", "85s",
        "76s", "75s", "74s",
        "65s", "64s",
        "54s", "53s",
        "43s",
        "AKo", "AQo", "AJo", "ATo", "A9o", "A8o", "A7o", "A6o", "A5o", "A4o",
        "KQo", "KJo", "KTo", "K9o",
        "QJo", "QTo", "Q9o",
        "JTo", "J9o",
        "T9o",
        "98o"
    },
    Position.SB: {
        # SB complete'e karşı (nadir durum)
        "AA", "KK", "QQ", "JJ", "TT", "99", "88", "77", "66", "55", "44", "33", "22",
        "AKs", "AQs", "AJs", "ATs", "A9s", "A8s", "A7s", "A6s", "A5s", "A4s", "A3s", "A2s",
        "KQs", "KJs", "KTs", "K9s", "K8s", "K7s", "K6s", "K5s", "K4s", "K3s", "K2s",
        "QJs", "QTs", "Q9s", "Q8s", "Q7s", "Q6s", "Q5s",
        "JTs", "J9s", "J8s", "J7s", "J6s",
        "T9s", "T8s", "T7s", "T6s",
        "98s", "97s", "96s", "95s",
        "87s", "86s", "85s",
        "76s", "75s", "74s",
        "65s", "64s", "63s",
        "54s", "53s", "52s",
        "43s", "42s",
        "32s",
        "AKo", "AQo", "AJo", "ATo", "A9o", "A8o", "A7o", "A6o", "A5o", "A4o", "A3o", "A2o",
        "KQo", "KJo", "KTo", "K9o", "K8o",
        "QJo", "QTo", "Q9o",
        "JTo", "J9o",
        "T9o", "T8o",
        "98o", "97o",
        "87o",
        "76o"
    }
}


# --- HELPER FUNCTIONS ---

def hand_to_notation(card1_rank: str, card2_rank: str, is_suited: bool) -> str:
    """
    İki kart rank'ını ve suited/offsuit durumunu notasyona çevirir.
    Örn: ('A', 'K', True) -> 'AKs'
    """
    from constants import RANK_VALUES
    
    # High card önce
    val1 = RANK_VALUES.get(card1_rank, 0)
    val2 = RANK_VALUES.get(card2_rank, 0)
    
    if val1 >= val2:
        high, low = card1_rank, card2_rank
    else:
        high, low = card2_rank, card1_rank
    
    # Pocket pair
    if high == low:
        return f"{high}{low}"
    
    # Suited veya Offsuit
    suffix = "s" if is_suited else "o"
    return f"{high}{low}{suffix}"


def is_hand_in_range(hand_notation: str, range_set: Set[str]) -> bool:
    """
    Verilen el notasyonu range içinde mi kontrol eder.
    """
    return hand_notation in range_set


def get_rfi_range(position: Position) -> Set[str]:
    """Pozisyon için RFI range'i döndürür."""
    return RFI_RANGES.get(position, set())


def get_3bet_range(vs_position: Position, include_bluffs: bool = True) -> Set[str]:
    """
    Belirli bir pozisyona karşı 3-bet range'i döndürür.
    """
    value_range = THREE_BET_VALUE.get(vs_position, set())
    if include_bluffs:
        bluff_range = THREE_BET_BLUFF.get(vs_position, set())
        return value_range | bluff_range
    return value_range


def get_bb_defense_range(vs_position: Position) -> Set[str]:
    """BB'den belirli pozisyona karşı defense range'i."""
    return BB_CALL_VS_POSITION.get(vs_position, set())


def calculate_range_percentage(range_set: Set[str]) -> float:
    """
    Range'in toplam el kombinasyonlarına oranını hesaplar.
    Toplam: 1326 el kombinasyonu
    - Pocket pair: 6 combo each (78 total for 13 pairs)
    - Suited: 4 combo each
    - Offsuit: 12 combo each
    """
    total_combos = 0
    
    for hand in range_set:
        if len(hand) == 2:  # Pocket pair (AA, KK, etc.)
            total_combos += 6
        elif hand.endswith('s'):  # Suited
            total_combos += 4
        elif hand.endswith('o'):  # Offsuit
            total_combos += 12
    
    return (total_combos / 1326) * 100


# --- RANGE INFO ---

def print_range_stats():
    """Tüm range'lerin istatistiklerini yazdırır."""
    print("=== PREFLOP RANGE STATISTICS ===\n")
    
    for pos in Position:
        if pos == Position.BB:
            continue
        rfi = get_rfi_range(pos)
        pct = calculate_range_percentage(rfi)
        print(f"{pos.name} RFI: {len(rfi)} hands ({pct:.1f}%)")
    
    print("\n=== 3-BET RANGES ===\n")
    for pos in Position:
        three_bet = get_3bet_range(pos)
        pct = calculate_range_percentage(three_bet)
        print(f"vs {pos.name}: {len(three_bet)} hands ({pct:.1f}%)")
    
    print("\n=== BB DEFENSE RANGES ===\n")
    for pos in [Position.UTG, Position.MP, Position.CO, Position.BTN]:
        defense = get_bb_defense_range(pos)
        pct = calculate_range_percentage(defense)
        print(f"vs {pos.name}: {len(defense)} hands ({pct:.1f}%)")


if __name__ == "__main__":
    print_range_stats()
