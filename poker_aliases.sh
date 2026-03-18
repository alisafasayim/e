#!/bin/bash
# Poker Tracker - Hızlı Komut Kısayolları
# Bu dosyayı shell'inize yükleyin: source poker_aliases.sh
# Veya .bashrc/.zshrc'ye ekleyin: source /home/user/et/poker_aliases.sh

POKER_DIR="/home/user/et"

# Ana komutlar
alias poker='cd $POKER_DIR && bash poker-tracker.sh'
alias poker-start='cd $POKER_DIR && python3 poker_tracker/main.py --config poker_tracker_config.json'
alias poker-cal='cd $POKER_DIR && python3 poker_tracker/main.py --auto-calibrate'
alias poker-console='cd $POKER_DIR && python3 poker_tracker/main.py --console --config poker_tracker_config.json'
alias poker-manual='cd $POKER_DIR && python3 poker_tracker/main.py --calibrate'
alias poker-debug='cd $POKER_DIR && python3 poker_tracker/main.py --debug --config poker_tracker_config.json'

# Ekran görüntüsünden kalibre et
poker-screenshot() {
    cd "$POKER_DIR" && python3 poker_tracker/main.py --auto-calibrate --image "$1"
}

echo "Poker Tracker kısayolları yüklendi:"
echo "  poker          → İnteraktif menü"
echo "  poker-start    → Overlay başlat"
echo "  poker-cal      → Otomatik kalibrasyon"
echo "  poker-console  → Terminal modu"
echo "  poker-manual   → Manuel kalibrasyon"
echo "  poker-debug    → Debug modu"
echo "  poker-screenshot <dosya> → Görüntüden kalibre et"
