"""
POKER BOT V4.0 - TEST SUITE
===========================
Bot test senaryoları.
"""

import logging
from typing import List

from constants import Position, Street, ActionType
from data_classes import (
    HoleCards, Board, GameState, PokerAction, PlayerStats
)
from poker_bot import PokerBot, BotConfig

# Debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger("Tests")


def create_game_state(
    board_cards: List[str],
    pot: float,
    hero_stack: float,
    current_bet: float = 0,
    hero_invested: float = 0,
    bb: float = 1.0
) -> GameState:
    """Test için GameState oluşturur."""
    board = Board.from_strings(board_cards) if board_cards else Board()
    
    return GameState(
        street=board.street,
        board=board,
        pot=pot,
        hero_stack=hero_stack,
        villain_stack=hero_stack,  # Basitlik için aynı
        current_bet=current_bet,
        hero_invested=hero_invested,
        big_blind=bb
    )


def test_preflop_decisions():
    """Preflop karar testleri."""
    print("\n" + "="*60)
    print("TEST: PREFLOP DECISIONS")
    print("="*60)
    
    config = BotConfig(use_human_timing=False, verbose=True)
    bot = PokerBot(config)
    
    # Test 1: Premium hand from UTG
    print("\n--- Test 1: AA from UTG, no action ---")
    bot.new_hand(["As", "Ah"], Position.UTG)
    state = create_game_state([], pot=1.5, hero_stack=100, current_bet=1.0)
    action = bot.decide(state)
    print(f"Result: {action}")
    assert action.action == ActionType.RAISE, "AA should raise"
    
    # Test 2: Weak hand from UTG
    print("\n--- Test 2: 72o from UTG ---")
    bot.new_hand(["7h", "2c"], Position.UTG)
    state = create_game_state([], pot=1.5, hero_stack=100, current_bet=1.0)
    action = bot.decide(state)
    print(f"Result: {action}")
    assert action.action == ActionType.FOLD, "72o should fold from UTG"
    
    # Test 3: Suited connector from BTN
    print("\n--- Test 3: 87s from BTN, folded to us ---")
    bot.new_hand(["8s", "7s"], Position.BTN)
    state = create_game_state([], pot=1.5, hero_stack=100, current_bet=1.0)
    action = bot.decide(state)
    print(f"Result: {action}")
    assert action.action == ActionType.RAISE, "87s should open from BTN"
    
    # Test 4: 3-bet spot
    print("\n--- Test 4: AKs vs CO raise ---")
    bot.new_hand(["Ah", "Kh"], Position.BTN)
    state = create_game_state([], pot=4.5, hero_stack=100, current_bet=3.0)
    state.villain_position = Position.CO
    action = bot.decide(state)
    print(f"Result: {action}")
    assert action.action == ActionType.RAISE, "AKs should 3-bet"
    
    print("\n✓ Preflop tests passed!")


def test_postflop_value_betting():
    """Postflop value bet testleri."""
    print("\n" + "="*60)
    print("TEST: POSTFLOP VALUE BETTING")
    print("="*60)
    
    config = BotConfig(use_human_timing=False)
    bot = PokerBot(config)
    
    # Test 1: Top pair on dry board
    print("\n--- Test 1: AK on K72 rainbow (Top Pair) ---")
    bot.new_hand(["Ah", "Kc"], Position.BTN)
    state = create_game_state(
        ["Ks", "7h", "2d"],  # Dry board
        pot=6.0,
        hero_stack=100,
        current_bet=0  # Checked to us
    )
    action = bot.decide(state)
    print(f"Result: {action}")
    assert action.action == ActionType.BET, "Should bet top pair"
    
    # Test 2: Set on wet board - bigger bet
    print("\n--- Test 2: 77 on 7s 8s 9h (Set on wet board) ---")
    bot.new_hand(["7h", "7c"], Position.BTN)
    state = create_game_state(
        ["7s", "8s", "9h"],  # Very wet
        pot=10.0,
        hero_stack=100,
        current_bet=0
    )
    action = bot.decide(state)
    print(f"Result: {action}")
    assert action.action == ActionType.BET, "Should bet set"
    # Wet board'da daha büyük bet
    assert action.amount > 5.0, "Should bet larger on wet board"
    
    print("\n✓ Value betting tests passed!")


def test_postflop_facing_bet():
    """Bet'e karşı karar testleri."""
    print("\n" + "="*60)
    print("TEST: FACING BET DECISIONS")
    print("="*60)
    
    config = BotConfig(use_human_timing=False)
    bot = PokerBot(config)
    
    # Test 1: Strong hand facing bet - raise
    print("\n--- Test 1: Set facing bet on dry board ---")
    bot.new_hand(["Kh", "Kc"], Position.BB)
    state = create_game_state(
        ["Ks", "7h", "2d"],
        pot=15.0,  # 10 pot + 5 bet
        hero_stack=95,
        current_bet=5.0
    )
    action = bot.decide(state)
    print(f"Result: {action}")
    # Set ile ya raise ya call (trap)
    assert action.action in [ActionType.RAISE, ActionType.CALL], "Should raise or trap"
    
    # Test 2: Marginal hand facing large bet - fold
    print("\n--- Test 2: Middle pair facing pot-sized bet ---")
    bot.new_hand(["8h", "8c"], Position.BB)
    state = create_game_state(
        ["Ks", "Qh", "2d"],  # Overcards
        pot=20.0,
        hero_stack=90,
        current_bet=10.0  # Pot-sized bet
    )
    action = bot.decide(state)
    print(f"Result: {action}")
    # 88 bu board'da zayıf, fold etmeli
    assert action.action == ActionType.FOLD, "Should fold underpair to pot bet"
    
    # Test 3: Draw with correct odds
    print("\n--- Test 3: Flush draw facing small bet ---")
    bot.new_hand(["Ah", "5h"], Position.BB)
    state = create_game_state(
        ["Kh", "7h", "2d"],  # Flush draw
        pot=12.0,  # 10 pot + 2 bet
        hero_stack=98,
        current_bet=2.0  # Small bet
    )
    action = bot.decide(state)
    print(f"Result: {action}")
    assert action.action in [ActionType.CALL, ActionType.RAISE], "Should call/raise with flush draw"
    
    print("\n✓ Facing bet tests passed!")


def test_board_texture_analysis():
    """Board texture analizi testleri."""
    print("\n" + "="*60)
    print("TEST: BOARD TEXTURE ANALYSIS")
    print("="*60)
    
    from hand_evaluator import BoardAnalyzer
    analyzer = BoardAnalyzer()
    
    # Test 1: Dry rainbow
    board1 = Board.from_strings(["Ks", "7h", "2d"])
    analysis1 = analyzer.analyze(board1)
    print(f"\nBoard: {board1}")
    print(f"Texture: {analysis1.texture.name}")
    print(f"Danger: {analysis1.danger_level}")
    print(f"Description: {analysis1.description}")
    assert "Rainbow" in analysis1.description
    
    # Test 2: Monotone
    board2 = Board.from_strings(["Ks", "7s", "2s"])
    analysis2 = analyzer.analyze(board2)
    print(f"\nBoard: {board2}")
    print(f"Texture: {analysis2.texture.name}")
    print(f"Danger: {analysis2.danger_level}")
    assert analysis2.danger_level >= 5, "Monotone should be high danger"
    
    # Test 3: Connected
    board3 = Board.from_strings(["9h", "8d", "7c"])
    analysis3 = analyzer.analyze(board3)
    print(f"\nBoard: {board3}")
    print(f"Texture: {analysis3.texture.name}")
    print(f"Danger: {analysis3.danger_level}")
    assert analysis3.straight_possible or analysis3.straight_draw_possible
    
    # Test 4: Paired
    board4 = Board.from_strings(["Ks", "Kh", "7d"])
    analysis4 = analyzer.analyze(board4)
    print(f"\nBoard: {board4}")
    print(f"Texture: {analysis4.texture.name}")
    print(f"Is Paired: {analysis4.is_paired}")
    assert analysis4.is_paired
    
    print("\n✓ Board texture tests passed!")


def test_opponent_adaptation():
    """Rakip adaptasyonu testleri."""
    print("\n" + "="*60)
    print("TEST: OPPONENT ADAPTATION")
    print("="*60)
    
    config = BotConfig(use_human_timing=False, use_exploits=True)
    bot = PokerBot(config)
    
    # Calling station rakip
    fish_stats = PlayerStats(
        player_id="fish1",
        hands_played=100,
        vpip=45.0,  # Çok loose
        pfr=8.0,    # Pasif
        aggression_factor=0.5,
        fold_to_cbet=20.0  # Çok az fold
    )
    
    bot.update_opponent_stats("fish1", fish_stats)
    
    print(f"\nVillain type: {fish_stats.player_type}")
    print(f"VPIP: {fish_stats.vpip}%, PFR: {fish_stats.pfr}%")
    print(f"Fold to C-bet: {fish_stats.fold_to_cbet}%")
    
    # Fish'e karşı value bet
    print("\n--- Test: Value bet vs calling station ---")
    bot.new_hand(["Ah", "Kc"], Position.BTN, villain_id="fish1")
    state = create_game_state(
        ["As", "7h", "2d"],
        pot=8.0,
        hero_stack=100,
        current_bet=0
    )
    action = bot.decide(state)
    print(f"Result: {action}")
    # Fish'e karşı büyük bet olmalı
    assert action.action == ActionType.BET
    
    print("\n✓ Opponent adaptation tests passed!")


def test_anti_detection():
    """Anti-detection testleri."""
    print("\n" + "="*60)
    print("TEST: ANTI-DETECTION FEATURES")
    print("="*60)
    
    from anti_detection import HumanTimer, MistakeMaker, BettingPatternVariator
    
    # Timing variance
    print("\n--- Test 1: Timing variance ---")
    timer = HumanTimer()
    times = [timer.get_think_time(Street.FLOP) for _ in range(10)]
    print(f"Think times (10 samples): {times}")
    assert len(set(times)) > 3, "Should have variance in timing"
    
    # Bet size variance
    print("\n--- Test 2: Bet size variance ---")
    variator = BettingPatternVariator()
    sizes = [variator.vary_bet_size(5.0, 10.0) for _ in range(10)]
    print(f"Varied sizes (base 5.0): {sizes}")
    assert min(sizes) != max(sizes), "Should vary bet sizes"
    
    # Human rounding
    print("\n--- Test 3: Human-like rounding ---")
    rounded = [variator.round_to_human_amount(17.43) for _ in range(5)]
    print(f"Rounded amounts: {rounded}")
    
    # Mistake making
    print("\n--- Test 4: Mistake frequency ---")
    mistake_maker = MistakeMaker(mistake_probability=0.10)  # %10 test için
    mistakes = sum(1 for _ in range(100) if mistake_maker.should_make_mistake())
    print(f"Mistakes in 100 decisions: {mistakes}")
    print(f"Stats: {mistake_maker.get_stats()}")
    
    print("\n✓ Anti-detection tests passed!")


def run_full_hand_simulation():
    """Tam bir el simülasyonu."""
    print("\n" + "="*60)
    print("FULL HAND SIMULATION")
    print("="*60)
    
    config = BotConfig(use_human_timing=False, verbose=True)
    bot = PokerBot(config)
    
    # Setup
    print("\n--- PREFLOP ---")
    bot.new_hand(["7s", "7h"], Position.BTN)
    
    state = create_game_state([], pot=1.5, hero_stack=100, current_bet=1.0)
    action = bot.decide(state)
    print(f"Hero: {action}")
    
    # Assume villain calls
    print("\n--- FLOP: 7d 8s 9s ---")
    state = create_game_state(
        ["7d", "8s", "9s"],  # Set on wet board
        pot=6.0,  # 3BB raise called
        hero_stack=97,
        current_bet=0
    )
    action = bot.decide(state)
    print(f"Hero: {action}")
    
    # Assume villain calls
    pot_after_flop = 6.0 + action.amount * 2
    
    print("\n--- TURN: 7d 8s 9s 2c ---")
    state = create_game_state(
        ["7d", "8s", "9s", "2c"],
        pot=pot_after_flop,
        hero_stack=97 - action.amount,
        current_bet=0
    )
    action = bot.decide(state)
    print(f"Hero: {action}")
    
    print("\n--- RIVER: 7d 8s 9s 2c Jd ---")
    pot_after_turn = pot_after_flop + action.amount * 2
    state = create_game_state(
        ["7d", "8s", "9s", "2c", "Jd"],  # Straight complete!
        pot=pot_after_turn,
        hero_stack=97 - action.amount * 2,
        current_bet=0
    )
    action = bot.decide(state)
    print(f"Hero: {action}")
    
    # End hand
    bot.end_hand(won=True, pot_size=pot_after_turn)
    
    print("\n--- SESSION STATS ---")
    print(bot.get_session_stats())


def main():
    """Tüm testleri çalıştır."""
    print("\n" + "="*60)
    print("POKER BOT V4.0 - TEST SUITE")
    print("="*60)
    
    try:
        test_board_texture_analysis()
        test_preflop_decisions()
        test_postflop_value_betting()
        test_postflop_facing_bet()
        test_opponent_adaptation()
        test_anti_detection()
        run_full_hand_simulation()
        
        print("\n" + "="*60)
        print("ALL TESTS PASSED! ✓")
        print("="*60)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        raise


if __name__ == "__main__":
    main()
