"""
POKER BOT V4.0 - HAND EVALUATOR
===============================
El gücü hesaplama ve board analizi.
Monte Carlo simülasyonu ile gerçek equity hesabı.
"""

from typing import List, Dict, Tuple, Optional, Set
from collections import Counter
from itertools import combinations
import random
import time

from constants import (
    RANKS, SUITS, RANK_VALUES, RANK_VALUES_LOW_ACE,
    BoardTexture, HandCategory, DrawType,
    MONTE_CARLO_ITERATIONS, SIMULATION_TIMEOUT
)
from data_classes import (
    Card, HoleCards, Board, HandStrength, BoardAnalysis
)

class HandEvaluator:
    """El değerlendirme motoru - Monte Carlo destekli."""
    
    def __init__(self):
        self._deck = self._create_deck()
    
    def _create_deck(self) -> List[Card]:
        """52 kartlık deste oluşturur."""
        return [Card(r, s) for r in RANKS for s in SUITS]
    
    def calculate_equity_monte_carlo(
        self, 
        hole_cards: HoleCards, 
        board: Board, 
        iterations: int = MONTE_CARLO_ITERATIONS
    ) -> float:
        """
        Monte Carlo simülasyonu ile gerçek equity hesaplar.
        
        Args:
            hole_cards: Hero'nun eli
            board: Mevcut board kartları
            iterations: Simülasyon sayısı
            
        Returns:
            0.0-1.0 arası kazanma ihtimali
        """
        if not hole_cards:
            return 0.5
        
        start_time = time.time()
        
        # Bilinen kartları belirle
        known_cards = {str(hole_cards.card1), str(hole_cards.card2)}
        known_cards.update(str(c) for c in board.cards)
        
        # Kalan desteyi oluştur
        deck = [c for c in self._deck if str(c) not in known_cards]
        
        wins = 0
        splits = 0
        cards_to_deal = 5 - len(board.cards)
        
        for i in range(iterations):
            # Timeout kontrolü
            if time.time() - start_time > SIMULATION_TIMEOUT:
                iterations = i  # Gerçek iterasyon sayısını güncelle
                break
            
            # Deste karıştır
            random.shuffle(deck)
            
            # Rakibe el ver (Heads-up)
            villain_cards = [deck[0], deck[1]]
            villain_hand = HoleCards(villain_cards[0], villain_cards[1])
            
            # Board'u tamamla
            sim_board_cards = board.cards + deck[2:2+cards_to_deal]
            sim_board = Board(sim_board_cards)
            
            # Elleri değerlendir
            hero_score = self._get_hand_score(hole_cards, sim_board)
            villain_score = self._get_hand_score(villain_hand, sim_board)
            
            if hero_score > villain_score:
                wins += 1
            elif hero_score == villain_score:
                splits += 1
        
        # Equity = (Kazanma + Beraberlik/2) / Toplam
        if iterations > 0:
            equity = (wins + (splits * 0.5)) / iterations
        else:
            equity = 0.5
            
        return round(equity, 3)
    
    def _get_hand_score(self, hole_cards: HoleCards, board: Board) -> Tuple[int, List[int]]:
        """7 karttan en iyi 5'liyi bulur ve skor döndürür."""
        all_cards = [hole_cards.card1, hole_cards.card2] + board.cards
        
        best_score = (-1, [])
        for combo in combinations(all_cards, 5):
            score = self._evaluate_5_card_hand(list(combo))
            if score > best_score:
                best_score = score
        
        return best_score
    
    def _evaluate_5_card_hand(self, cards: List[Card]) -> Tuple[int, List[int]]:
        """5 kartlık eli değerlendirir."""
        cards.sort(key=lambda c: c.value, reverse=True)
        ranks = [c.value for c in cards]
        suits = [c.suit for c in cards]
        
        is_flush = len(set(suits)) == 1
        
        # Straight kontrolü
        is_straight = False
        unique_ranks = sorted(list(set(ranks)), reverse=True)
        if len(unique_ranks) == 5:
            if unique_ranks[0] - unique_ranks[4] == 4:
                is_straight = True
            # Wheel (A-2-3-4-5)
            if set(unique_ranks) == {14, 5, 4, 3, 2}:
                is_straight = True
                ranks = [5, 4, 3, 2, 1]
        
        rank_counts = Counter(ranks)
        counts = sorted(rank_counts.values(), reverse=True)
        sorted_ranks = sorted(rank_counts.keys(), key=lambda r: (rank_counts[r], r), reverse=True)
        
        # El kategorisi belirleme
        if is_straight and is_flush:
            return (9, ranks)  # Straight Flush
        if counts == [4, 1]:
            return (8, sorted_ranks)  # Four of a Kind
        if counts == [3, 2]:
            return (7, sorted_ranks)  # Full House
        if is_flush:
            return (6, ranks)  # Flush
        if is_straight:
            return (5, ranks)  # Straight
        if counts == [3, 1, 1]:
            return (4, sorted_ranks)  # Three of a Kind
        if counts == [2, 2, 1]:
            return (3, sorted_ranks)  # Two Pair
        if counts == [2, 1, 1, 1]:
            return (2, sorted_ranks)  # Pair
        
        return (1, ranks)  # High Card
    
    def evaluate_hand(self, hole_cards: HoleCards, board: Board, use_monte_carlo: bool = False) -> HandStrength:
        """
        5-7 kart arasından en iyi 5'li eli bulur ve değerlendirir.
        use_monte_carlo=True ise gerçek Monte Carlo equity hesaplar.
        """
        all_cards = [hole_cards.card1, hole_cards.card2] + board.cards
        
        if len(all_cards) < 5:
            # Preflop - sadece hole cards değerlendirmesi
            return self._evaluate_preflop(hole_cards)
        
        # Tüm 5'li kombinasyonları dene
        best_hand = None
        best_score = -1
        uses_both = False
        
        for combo in combinations(all_cards, 5):
            score, category, desc = self._score_five_cards(list(combo))
            if score > best_score:
                best_score = score
                best_hand = (score, category, desc, combo)
                # Her iki hole card da kullanılıyor mu?
                uses_both = (hole_cards.card1 in combo and hole_cards.card2 in combo)
        
        if best_hand is None:
            return HandStrength()
        
        score, category, desc, combo = best_hand
        
        # Draw analizi (sadece flop/turn'de)
        draw_type, draw_outs = self._analyze_draws(hole_cards, board)
        
        # Nut analizi
        is_nut = self._is_nut_hand(hole_cards, board, category)
        
        # Vulnerability analizi
        vulnerable = self._is_vulnerable(category, board)
        
        # Equity hesabı
        if use_monte_carlo and len(board.cards) >= 3:
            # Monte Carlo ile gerçek equity (postflop)
            equity = self.calculate_equity_monte_carlo(hole_cards, board, iterations=500)
        else:
            # Hızlı tahmin
            equity = self._estimate_equity(category, score, board)
        
        return HandStrength(
            equity=equity,
            hand_category=category,
            hand_rank=score,
            is_made_hand=(category.value >= HandCategory.PAIR.value),
            made_hand_desc=desc,
            has_draw=(draw_type != DrawType.NONE),
            draw_type=draw_type,
            draw_outs=draw_outs,
            draw_equity=draw_outs * 0.02 if board.street == Street.TURN else draw_outs * 0.04,
            is_nut=is_nut,
            uses_both_cards=uses_both,
            vulnerable=vulnerable
        )
    
    def _evaluate_preflop(self, hole_cards: HoleCards) -> HandStrength:
        """Preflop el gücü tahmini."""
        h = hole_cards
        
        # Premium pairs
        if h.is_pocket_pair:
            pair_val = h.card1.value
            if pair_val >= 13:  # AA, KK
                return HandStrength(equity=0.85, is_made_hand=True, made_hand_desc=f"Pocket {h.card1.rank}s")
            elif pair_val >= 10:  # QQ, JJ, TT
                return HandStrength(equity=0.75, is_made_hand=True, made_hand_desc=f"Pocket {h.card1.rank}s")
            else:
                return HandStrength(equity=0.55 + pair_val * 0.01, is_made_hand=True, 
                                  made_hand_desc=f"Pocket {h.card1.rank}s")
        
        # Suited broadways
        high_val = h.high_card.value
        low_val = h.low_card.value
        
        if h.is_suited:
            if high_val == 14:  # Ax suited
                if low_val >= 10:  # AKs, AQs, AJs, ATs
                    return HandStrength(equity=0.67, made_hand_desc=f"{h}s Premium Suited")
                else:
                    return HandStrength(equity=0.55, made_hand_desc=f"{h}s Suited Ace")
            elif high_val >= 12 and low_val >= 10:  # KQs, KJs, QJs etc
                return HandStrength(equity=0.60, made_hand_desc=f"{h}s Suited Broadway")
            elif h.is_connected or h.gap <= 1:  # Suited connectors
                return HandStrength(equity=0.45, has_draw=True, made_hand_desc=f"{h}s Suited Connector")
        
        # Offsuit broadways
        if high_val == 14 and low_val >= 12:  # AK, AQ
            return HandStrength(equity=0.62, made_hand_desc=f"{h} Broadway")
        elif high_val >= 12 and low_val >= 10:
            return HandStrength(equity=0.52, made_hand_desc=f"{h} Offsuit Broadway")
        
        # Diğer eller
        return HandStrength(equity=0.35, made_hand_desc=f"{h} Speculative")

    def _score_five_cards(self, cards: List[Card]) -> Tuple[int, HandCategory, str]:
        """
        5 kartı değerlendirir ve skor döndürür.
        Skor formatı: CATEGORY * 10^10 + TIE_BREAKERS
        """
        ranks = [c.rank for c in cards]
        suits = [c.suit for c in cards]
        values = sorted([c.value for c in cards], reverse=True)
        
        rank_counts = Counter(ranks)
        suit_counts = Counter(suits)
        
        is_flush = max(suit_counts.values()) == 5
        is_straight, straight_high = self._check_straight(values)
        
        # Royal Flush
        if is_flush and is_straight and straight_high == 14:
            return (10 * 10**10, HandCategory.ROYAL_FLUSH, "Royal Flush")
        
        # Straight Flush
        if is_flush and is_straight:
            return (9 * 10**10 + straight_high, HandCategory.STRAIGHT_FLUSH, 
                   f"Straight Flush, {self._val_to_rank(straight_high)} high")
        
        # Four of a Kind
        quads = [r for r, c in rank_counts.items() if c == 4]
        if quads:
            quad_val = RANK_VALUES[quads[0]]
            kicker = max(v for v in values if v != quad_val)
            score = 8 * 10**10 + quad_val * 10**6 + kicker
            return (score, HandCategory.FOUR_OF_A_KIND, f"Quad {quads[0]}s")
        
        # Full House
        trips = [r for r, c in rank_counts.items() if c == 3]
        pairs = [r for r, c in rank_counts.items() if c == 2]
        if trips and pairs:
            trip_val = RANK_VALUES[trips[0]]
            pair_val = RANK_VALUES[pairs[0]]
            score = 7 * 10**10 + trip_val * 10**6 + pair_val
            return (score, HandCategory.FULL_HOUSE, f"Full House, {trips[0]}s full of {pairs[0]}s")
        
        # Flush
        if is_flush:
            score = 6 * 10**10 + self._kickers_score(values)
            return (score, HandCategory.FLUSH, f"Flush, {self._val_to_rank(values[0])} high")
        
        # Straight
        if is_straight:
            score = 5 * 10**10 + straight_high
            return (score, HandCategory.STRAIGHT, f"Straight, {self._val_to_rank(straight_high)} high")
        
        # Three of a Kind
        if trips:
            trip_val = RANK_VALUES[trips[0]]
            kickers = sorted([v for v in values if v != trip_val], reverse=True)[:2]
            score = 4 * 10**10 + trip_val * 10**6 + self._kickers_score(kickers)
            return (score, HandCategory.THREE_OF_A_KIND, f"Trip {trips[0]}s")
        
        # Two Pair
        if len(pairs) >= 2:
            pair_vals = sorted([RANK_VALUES[p] for p in pairs], reverse=True)[:2]
            kicker = max(v for v in values if v not in pair_vals)
            score = 3 * 10**10 + pair_vals[0] * 10**6 + pair_vals[1] * 10**4 + kicker
            return (score, HandCategory.TWO_PAIR, 
                   f"Two Pair, {self._val_to_rank(pair_vals[0])}s and {self._val_to_rank(pair_vals[1])}s")
        
        # One Pair
        if pairs:
            pair_val = RANK_VALUES[pairs[0]]
            kickers = sorted([v for v in values if v != pair_val], reverse=True)[:3]
            score = 2 * 10**10 + pair_val * 10**6 + self._kickers_score(kickers)
            return (score, HandCategory.PAIR, f"Pair of {pairs[0]}s")
        
        # High Card
        score = 1 * 10**10 + self._kickers_score(values)
        return (score, HandCategory.HIGH_CARD, f"{self._val_to_rank(values[0])} high")
    
    def _check_straight(self, values: List[int]) -> Tuple[bool, int]:
        """Straight kontrolü. Wheel (A2345) dahil."""
        unique_vals = sorted(set(values), reverse=True)
        
        # Normal straight
        if len(unique_vals) >= 5:
            for i in range(len(unique_vals) - 4):
                if unique_vals[i] - unique_vals[i+4] == 4:
                    return True, unique_vals[i]
        
        # Wheel (A2345)
        if set([14, 5, 4, 3, 2]).issubset(set(values)):
            return True, 5  # 5-high straight
        
        return False, 0
    
    def _kickers_score(self, values: List[int]) -> int:
        """Kicker'ları skorlar (her biri 2 haneli)."""
        score = 0
        for i, v in enumerate(values[:5]):
            score += v * (100 ** (4 - i))
        return score
    
    def _val_to_rank(self, val: int) -> str:
        """Değeri rank'a çevirir (14 -> 'A')."""
        for r, v in RANK_VALUES.items():
            if v == val:
                return r
        return '?'
    
    def _analyze_draws(self, hole_cards: HoleCards, board: Board) -> Tuple[DrawType, int]:
        """Draw analizi yapar."""
        if board.street == Street.RIVER:
            return DrawType.NONE, 0
        
        all_cards = [hole_cards.card1, hole_cards.card2] + board.cards
        suits = [c.suit for c in all_cards]
        values = sorted([c.value for c in all_cards])
        
        # Flush draw
        suit_counts = Counter(suits)
        max_suit_count = max(suit_counts.values())
        flush_draw = max_suit_count == 4
        
        # Straight draw
        oesd = False  # Open-ended straight draw
        gutshot = False
        unique_vals = sorted(set(values))
        
        # 4 ardışık kart kontrolü (OESD)
        for i in range(len(unique_vals) - 3):
            window = unique_vals[i:i+4]
            if window[-1] - window[0] == 3:  # 4 ardışık
                oesd = True
                break
            elif window[-1] - window[0] == 4 and len(window) == 4:  # 1 gap = gutshot
                gutshot = True
        
        # Combo draw (flush + straight draw)
        if flush_draw and oesd:
            return DrawType.COMBO_DRAW, 15  # ~15 out
        elif flush_draw:
            return DrawType.FLUSH_DRAW, 9
        elif oesd:
            return DrawType.OESD, 8
        elif gutshot:
            return DrawType.GUTSHOT, 4
        
        # Backdoor draws (sadece flop'ta)
        if board.street == Street.FLOP:
            if max_suit_count == 3:
                return DrawType.BACKDOOR_FLUSH, 1
        
        return DrawType.NONE, 0
    
    def _is_nut_hand(self, hole_cards: HoleCards, board: Board, category: HandCategory) -> bool:
        """Nut el mi kontrolü (basitleştirilmiş)."""
        if category in [HandCategory.ROYAL_FLUSH, HandCategory.STRAIGHT_FLUSH]:
            return True
        if category == HandCategory.FOUR_OF_A_KIND:
            # Board'da trips varsa nut quad check
            return True  # Basitleştirilmiş
        if category == HandCategory.FLUSH:
            # Ace-high flush mu?
            all_cards = [hole_cards.card1, hole_cards.card2] + board.cards
            suit_counts = Counter(c.suit for c in all_cards)
            flush_suit = max(suit_counts.keys(), key=lambda s: suit_counts[s])
            flush_cards = [c for c in all_cards if c.suit == flush_suit]
            if any(c.rank == 'A' for c in flush_cards):
                if hole_cards.card1.suit == flush_suit and hole_cards.card1.rank == 'A':
                    return True
                if hole_cards.card2.suit == flush_suit and hole_cards.card2.rank == 'A':
                    return True
        return False
    
    def _is_vulnerable(self, category: HandCategory, board: Board) -> bool:
        """El kolayca geçilebilir mi?"""
        if category in [HandCategory.PAIR, HandCategory.TWO_PAIR]:
            return True
        if category == HandCategory.THREE_OF_A_KIND:
            # Board'da pair varsa (trips board) vulnerable değil
            board_ranks = [c.rank for c in board.cards]
            if len(board_ranks) != len(set(board_ranks)):
                return False  # Board paired - set olması güçlü
            return True  # Open trips - vulnerable
        return False
    
    def _estimate_equity(self, category: HandCategory, score: int, board: Board) -> float:
        """Basit equity tahmini (HU için)."""
        base_equity = {
            HandCategory.HIGH_CARD: 0.25,
            HandCategory.PAIR: 0.50,
            HandCategory.TWO_PAIR: 0.70,
            HandCategory.THREE_OF_A_KIND: 0.80,
            HandCategory.STRAIGHT: 0.85,
            HandCategory.FLUSH: 0.88,
            HandCategory.FULL_HOUSE: 0.95,
            HandCategory.FOUR_OF_A_KIND: 0.98,
            HandCategory.STRAIGHT_FLUSH: 0.99,
            HandCategory.ROYAL_FLUSH: 1.0
        }
        return base_equity.get(category, 0.25)


class BoardAnalyzer:
    """Board texture analizi."""
    
    def analyze(self, board: Board) -> BoardAnalysis:
        """Board'u analiz eder ve BoardAnalysis döndürür."""
        if not board.cards:
            return BoardAnalysis(texture=BoardTexture.UNKNOWN)
        
        cards = board.cards
        ranks = [c.rank for c in cards]
        suits = [c.suit for c in cards]
        values = sorted([c.value for c in cards], reverse=True)
        
        # Suit analizi
        suit_counts = Counter(suits)
        max_same_suit = max(suit_counts.values())
        flush_suit = max(suit_counts.keys(), key=lambda s: suit_counts[s])
        
        # Pairing analizi
        rank_counts = Counter(ranks)
        pairs = [r for r, c in rank_counts.items() if c == 2]
        trips = [r for r, c in rank_counts.items() if c == 3]
        
        is_paired = len(pairs) > 0
        is_double_paired = len(pairs) >= 2
        is_trips = len(trips) > 0
        
        # Straight potansiyeli
        unique_vals = sorted(set(values))
        gaps = sum(1 for i in range(len(unique_vals)-1) if unique_vals[i+1] - unique_vals[i] > 1)
        max_gap = max((unique_vals[i+1] - unique_vals[i] for i in range(len(unique_vals)-1)), default=0)
        
        # Broadway sayısı
        broadway_count = sum(1 for v in values if v >= 10)
        
        # Flush analizi
        flush_possible = max_same_suit >= 3 and len(cards) >= 3
        flush_draw_possible = max_same_suit >= 2
        
        # Straight analizi
        range_span = max(values) - min(values) if values else 0
        straight_possible = range_span <= 4 and len(unique_vals) >= 3 and not is_paired
        straight_draw_possible = range_span <= 5 and gaps <= 2
        
        # Tehlike seviyesi hesabı
        danger = 0
        if flush_possible:
            danger += 3
        elif flush_draw_possible:
            danger += 1
        if straight_possible:
            danger += 3
        elif straight_draw_possible:
            danger += 2
        if is_paired:
            danger += 1
        if is_trips:
            danger += 2
        if broadway_count >= 2:
            danger += 1
        
        # Texture belirleme
        texture = self._determine_texture(
            max_same_suit, is_paired, is_trips,
            straight_possible, straight_draw_possible,
            gaps, len(cards)
        )
        
        # Açıklama oluştur
        desc_parts = []
        if is_trips:
            desc_parts.append(f"Trips {trips[0]}")
        elif is_paired:
            desc_parts.append(f"Paired ({pairs[0]})")
        if max_same_suit >= 3:
            desc_parts.append("Monotone" if max_same_suit >= 3 else "Two-tone")
        elif max_same_suit == 2:
            desc_parts.append("Two-tone")
        else:
            desc_parts.append("Rainbow")
        if straight_possible:
            desc_parts.append("Connected")
        elif gaps <= 1:
            desc_parts.append("Semi-connected")
        
        description = " | ".join(desc_parts)
        
        return BoardAnalysis(
            texture=texture,
            flush_possible=flush_possible,
            flush_draw_possible=flush_draw_possible,
            flush_suit=flush_suit if max_same_suit >= 2 else None,
            same_suit_count=max_same_suit,
            straight_possible=straight_possible,
            straight_draw_possible=straight_draw_possible,
            connected_count=len(cards) - gaps,
            is_paired=is_paired,
            is_double_paired=is_double_paired,
            is_trips=is_trips,
            pair_rank=pairs[0] if pairs else None,
            highest_card=cards[0] if cards else None,
            broadway_count=broadway_count,
            danger_level=min(danger, 10),
            description=description
        )
    
    def _determine_texture(self, same_suit: int, paired: bool, trips: bool,
                          straight_poss: bool, straight_draw: bool, 
                          gaps: int, num_cards: int) -> BoardTexture:
        """Board texture kategorisini belirler."""
        
        if trips:
            return BoardTexture.TRIPS_BOARD
        
        if paired:
            return BoardTexture.PAIRED
        
        # Monotone (3+ aynı suit)
        if same_suit >= 3:
            return BoardTexture.VERY_WET
        
        # Çok bağlantılı
        if straight_poss and same_suit >= 2:
            return BoardTexture.VERY_WET
        
        if straight_poss:
            return BoardTexture.WET_STRAIGHTY
        
        if same_suit >= 2 and straight_draw:
            return BoardTexture.WET_FLUSHY
        
        if same_suit >= 2:
            return BoardTexture.SEMI_WET if gaps <= 2 else BoardTexture.DRY_TWOTONE
        
        # Rainbow
        if gaps <= 1:
            return BoardTexture.SEMI_WET
        
        return BoardTexture.DRY_RAINBOW


# Import için gerekli (dosya başında olmalı ama append ediyoruz)
from constants import Street
