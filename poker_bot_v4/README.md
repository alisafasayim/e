# Poker Bot V4.0

## Geliştirmeler (V3.3 -> V4.0)

### 1. Mimari İyileştirmeler
- **Modüler Yapı**: 6 ayrı modüle ayrıldı
- **Type Hints**: Tam tip desteği
- **Dataclasses**: Temiz veri yapıları
- **Logging**: Kapsamlı debug desteği

### 2. Preflop Stratejisi
- **GTO Range Tabloları**: Pozisyon bazlı RFI, 3-bet, BB defense range'leri
- **Suited/Offsuit Ayrımı**: AKs vs AKo farklı muamele
- **Pozisyon Farkındalığı**: UTG'den sıkı, BTN'den geniş

### 3. El Değerlendirme
- **Tam Hand Evaluator**: Tüm poker ellerini doğru değerlendirir
- **Draw Analizi**: OESD, Flush Draw, Gutshot, Combo Draw
- **Nut Analizi**: En iyi el kontrolü
- **Vulnerability Analizi**: Geçilmesi kolay eller

### 4. Board Texture Analizi
- **Paired Board Desteği**: K72 vs KK2 farkı
- **Flush/Straight Potansiyeli**: Tehlike seviyesi hesabı
- **Danger Level**: 0-10 arası board tehlike skoru

### 5. Dinamik Bet Sizing
- **SPR Bazlı**: Stack-to-Pot ratio'ya göre ayarlama
- **Texture Bazlı**: Islak/kuru board farkı
- **Opponent Bazlı**: Rakip tipine göre sizing

### 6. Anti-Detection Sistemi
- **Log-Normal Timing**: İnsansı düşünme süreleri
- **Kasıtlı Hatalar**: %3 sub-optimal karar
- **Tilt Simülasyonu**: Kayıp sonrası davranış değişikliği
- **Bet Variance**: Aynı durumda farklı bet miktarları

## Dosya Yapısı

```
poker_bot_v4/
├── constants.py       # Enum'lar ve sabitler
├── data_classes.py    # Veri yapıları (Card, Board, GameState vb.)
├── hand_evaluator.py  # El değerlendirme motoru
├── preflop_ranges.py  # GTO preflop range tabloları
├── strategy.py        # Preflop ve Postflop strateji
├── anti_detection.py  # İnsan benzeri davranış
├── bot.py            # Ana bot sınıfı
├── tests.py          # Test senaryoları
└── README.md         # Bu dosya
```

## Kullanım

```python
from bot import PokerBot, BotConfig, GameController
from constants import Position, ActionType

# Bot oluştur
config = BotConfig(
    small_blind=0.5,
    big_blind=1.0,
    use_anti_detection=True
)
bot = PokerBot(config)

# El simüle et
controller = GameController(bot)
actions = controller.run_hand(
    hero_hand=["Ah", "Kh"],
    board_sequence=[
        [],
        ["Qh", "Jh", "2d"],
        ["Qh", "Jh", "2d", "5c"],
        ["Qh", "Jh", "2d", "5c", "Th"]
    ],
    villain_actions=[
        (ActionType.RAISE, 2.5),
        (ActionType.CHECK, 0.0),
        (ActionType.BET, 5.0),
        (ActionType.CHECK, 0.0),
    ],
    pot_sequence=[3.5, 8.0, 18.0, 36.0],
    hero_position=Position.BTN,
    hero_stack=100.0
)
```

## Test

```bash
python tests.py
```

## TODO (Gelecek Geliştirmeler)
- [ ] Monte Carlo equity hesabı (treys entegrasyonu)
- [ ] Multi-way pot desteği
- [ ] ICM hesabı (turnuva desteği)
- [ ] Opponent modeling database
- [ ] Hand history parser
- [ ] Real-time integration

## V3.3'ten Düzeltilen Sorunlar

1. ✅ Board texture'da paired board algılama
2. ✅ Preflop'ta suited/offsuit ayrımı
3. ✅ Pot odds hesabı düzeltildi
4. ✅ `should_make_mistake()` fonksiyonu aktif edildi
5. ✅ SPR bazlı strateji eklendi
6. ✅ Pozisyon bazlı range'ler eklendi
