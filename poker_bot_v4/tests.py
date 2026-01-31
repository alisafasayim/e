"""
POKER BOT V4.0 - TEST SUITE
===========================
Kapsamlı test senaryoları.
"""

import logging
from constants import Position, ActionType
from bot import PokerBot, BotConfig, GameController

# Verbose logging for tests
logging.getLogger("PokerBot_v4").setLevel(logging.DEBUG)
logging.getLogger("Strategy").setLevel(logging.DEBUG)


def test_scenario_1_premium_hand():
    """
    Senaryo 1: Premium El (AA) - Value Extraction
    Hero: AA @ BTN
    Flop: Kc 7h 2d (Kuru board)
    Beklenti: Agresif value betting
    """
    print("\n" + "="*60)
    print("TEST 1: Premium Hand - AA on Dry Board")
    print("="*60)
    
    config = BotConfig(use_anti_detection=False, verbose=True)
    bot = PokerBot(config)
    controller = GameController(bot)
    
    actions = controller.run_hand(
        hero_hand=["Ah", "As"],
        board_sequence=[
            [],                          # Preflop
            ["Kc", "7h", "2d"],          # Flop (Dry)
            ["Kc", "7h", "2d", "5s"],    # Turn
            ["Kc", "7h", "2d", "5s", "Jd"]  # River
        ],
        villain_actions=[
            (ActionType.RAISE, 2.5),    # Preflop raise
            (ActionType.CHECK, 0.0),    # Flop check
            (ActionType.CALL, 5.0),     # Turn call (simulated)
            (ActionType.CHECK, 0.0),    # River check
        ],
        pot_sequence=[3.5, 8.0, 18.0, 36.0],
        hero_position=Position.BTN,
        hero_stack=100.0
    )
    
    print(f"\nActions taken: {[str(a) for a in actions]}")
    return actions


def test_scenario_2_set_on_wet_board():
    """
    Senaryo 2: Set on Wet Board
    Hero: 7s 7h @ CO
    Flop: 8s 9s 7d (Çok ıslak - Flush ve Straight draw)
    Beklenti: Büyük bet ile protection
    """
    print("\n" + "="*60)
    print("TEST 2: Set on Very Wet Board")
    print("="*60)
    
    config = BotConfig(use_anti_detection=False)
    bot = PokerBot(config)
    controller = GameController(bot)
    
    actions = controller.run_hand(
        hero_hand=["7s", "7h"],
        board_sequence=[
            [],
            ["8s", "9s", "7d"],
            ["8s", "9s", "7d", "2c"],
            ["8s", "9s", "7d", "2c", "Jh"]
        ],
        villain_actions=[
            (ActionType.RAISE, 2.5),
            (ActionType.BET, 4.0),      # Donk bet
            (ActionType.CHECK, 0.0),
            (ActionType.BET, 15.0),     # River bet
        ],
        pot_sequence=[3.5, 12.0, 24.0, 45.0],
        hero_position=Position.CO,
        hero_stack=100.0
    )
    
    print(f"\nActions taken: {[str(a) for a in actions]}")
    return actions


def test_scenario_3_flush_draw():
    """
    Senaryo 3: Flush Draw
    Hero: Ah Kh @ BTN
    Flop: 9h 4h 2c (Flush draw)
    Beklenti: Semi-bluff veya call
    """
    print("\n" + "="*60)
    print("TEST 3: Nut Flush Draw")
    print("="*60)
    
    config = BotConfig(use_anti_detection=False)
    bot = PokerBot(config)
    controller = GameController(bot)
    
    actions = controller.run_hand(
        hero_hand=["Ah", "Kh"],
        board_sequence=[
            [],
            ["9h", "4h", "2c"],
            ["9h", "4h", "2c", "7s"],
            ["9h", "4h", "2c", "7s", "3h"]  # Flush geldi!
        ],
        villain_actions=[
            (ActionType.RAISE, 2.5),
            (ActionType.BET, 5.0),
            (ActionType.BET, 12.0),
            (ActionType.CHECK, 0.0),
        ],
        pot_sequence=[3.5, 12.0, 32.0, 56.0],
        hero_position=Position.BTN,
        hero_stack=100.0
    )
    
    print(f"\nActions taken: {[str(a) for a in actions]}")
    return actions


def test_scenario_4_marginal_hand():
    """
    Senaryo 4: Marginal Hand (Top Pair Bad Kicker)
    Hero: A4o @ BB
    Flop: A 8 3 rainbow
    Beklenti: Pot control, küçük bet veya check-call
    """
    print("\n" + "="*60)
    print("TEST 4: Marginal Hand - Top Pair Bad Kicker")
    print("="*60)
    
    config = BotConfig(use_anti_detection=False)
    bot = PokerBot(config)
    controller = GameController(bot)
    
    actions = controller.run_hand(
        hero_hand=["Ac", "4d"],
        board_sequence=[
            [],
            ["As", "8h", "3d"],
            ["As", "8h", "3d", "Jc"],
            ["As", "8h", "3d", "Jc", "2s"]
        ],
        villain_actions=[
            (ActionType.RAISE, 2.5),
            (ActionType.BET, 4.0),
            (ActionType.BET, 10.0),
            (ActionType.BET, 25.0),
        ],
        pot_sequence=[5.0, 12.0, 28.0, 55.0],
        hero_position=Position.BB,
        hero_stack=100.0
    )
    
    print(f"\nActions taken: {[str(a) for a in actions]}")
    return actions


def test_scenario_5_bluff_catcher():
    """
    Senaryo 5: Bluff Catcher Situation
    Hero: JJ @ MP
    Flop: Q 8 2 rainbow
    Beklenti: Check/Call line, river karar
    """
    print("\n" + "="*60)
    print("TEST 5: Bluff Catcher - Pocket Jacks")
    print("="*60)
    
    config = BotConfig(use_anti_detection=False)
    bot = PokerBot(config)
    controller = GameController(bot)
    
    actions = controller.run_hand(
        hero_hand=["Jh", "Jd"],
        board_sequence=[
            [],
            ["Qc", "8h", "2d"],
            ["Qc", "8h", "2d", "5s"],
            ["Qc", "8h", "2d", "5s", "3c"]
        ],
        villain_actions=[
            (ActionType.CALL, 2.5),     # Cold call
            (ActionType.CHECK, 0.0),
            (ActionType.BET, 8.0),
            (ActionType.BET, 20.0),     # River overbet bluff?
        ],
        pot_sequence=[5.5, 12.0, 28.0, 48.0],
        hero_position=Position.MP,
        hero_stack=100.0
    )
    
    print(f"\nActions taken: {[str(a) for a in actions]}")
    return actions


def test_preflop_ranges():
    """
    Preflop range testleri.
    """
    print("\n" + "="*60)
    print("TEST: Preflop Range Statistics")
    print("="*60)
    
    from preflop_ranges import print_range_stats
    print_range_stats()


def test_anti_detection():
    """
    Anti-detection sistem testi.
    """
    print("\n" + "="*60)
    print("TEST: Anti-Detection System")
    print("="*60)
    
    config = BotConfig(
        use_anti_detection=True,
        mistake_probability=0.10  # Test için yüksek
    )
    bot = PokerBot(config)
    controller = GameController(bot)
    
    # 10 el oyna ve istatistikleri göster
    for i in range(10):
        print(f"\n--- Test Hand {i+1} ---")
        controller.run_hand(
            hero_hand=["Ah", "Kd"],
            board_sequence=[
                [],
                ["Qc", "Jh", "Td"],
                ["Qc", "Jh", "Td", "2s"],
                ["Qc", "Jh", "Td", "2s", "7c"]
            ],
            villain_actions=[
                (ActionType.RAISE, 2.5),
                (ActionType.CHECK, 0.0),
                (ActionType.CALL, 5.0),
                (ActionType.CHECK, 0.0),
            ],
            pot_sequence=[3.5, 8.0, 18.0, 36.0],
            hero_position=Position.BTN,
            hero_stack=100.0
        )
    
    print(f"\nBot Stats: {bot.get_stats()}")


def run_all_tests():
    """Tüm testleri çalıştır."""
    test_preflop_ranges()
    test_scenario_1_premium_hand()
    test_scenario_2_set_on_wet_board()
    test_scenario_3_flush_draw()
    test_scenario_4_marginal_hand()
    test_scenario_5_bluff_catcher()
    test_anti_detection()
    
    print("\n" + "="*60)
    print("ALL TESTS COMPLETED")
    print("="*60)


if __name__ == "__main__":
    run_all_tests()
