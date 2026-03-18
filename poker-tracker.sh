#!/bin/bash
# ═══════════════════════════════════════════════════════════
#  POKER TRACKER - Hızlı Başlatıcı
# ═══════════════════════════════════════════════════════════
#
# Kullanım:
#   ./poker-tracker.sh                → Otomatik kalibre et + başlat
#   ./poker-tracker.sh start          → Tracker'ı başlat (mevcut config ile)
#   ./poker-tracker.sh calibrate      → Otomatik kalibrasyon
#   ./poker-tracker.sh manual         → Manuel kalibrasyon
#   ./poker-tracker.sh console        → Terminal modunda başlat
#   ./poker-tracker.sh screenshot     → Ekran görüntüsünden kalibre et
#
# ═══════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TRACKER_DIR="/home/user/et/poker_tracker"
CONFIG_FILE="poker_tracker_config.json"
PYTHON="python3"

cd "$TRACKER_DIR/.." || exit 1

show_menu() {
    clear
    echo "╔══════════════════════════════════════════════════╗"
    echo "║          🃏 POKER TRACKER LAUNCHER 🃏            ║"
    echo "╠══════════════════════════════════════════════════╣"
    echo "║                                                  ║"
    echo "║  [1] Otomatik Kalibre Et + Başlat               ║"
    echo "║  [2] Tracker'ı Başlat (GUI Overlay)             ║"
    echo "║  [3] Tracker'ı Başlat (Terminal Modu)           ║"
    echo "║  [4] Otomatik Kalibrasyon                       ║"
    echo "║  [5] Ekran Görüntüsünden Kalibre Et            ║"
    echo "║  [6] Manuel Kalibrasyon                         ║"
    echo "║  [7] Çıkış                                      ║"
    echo "║                                                  ║"
    echo "╚══════════════════════════════════════════════════╝"
    echo ""
    read -rp "  Seçiminiz [1-7]: " choice
    echo ""
}

auto_calibrate_and_start() {
    echo ">>> Otomatik kalibrasyon başlatılıyor..."
    $PYTHON poker_tracker/main.py --auto-calibrate
    if [ -f "$CONFIG_FILE" ]; then
        echo ""
        echo ">>> Tracker başlatılıyor..."
        $PYTHON poker_tracker/main.py --config "$CONFIG_FILE"
    else
        echo "HATA: Konfigürasyon dosyası oluşturulamadı."
    fi
}

start_tracker() {
    if [ -f "$CONFIG_FILE" ]; then
        echo ">>> Tracker başlatılıyor (GUI)..."
        $PYTHON poker_tracker/main.py --config "$CONFIG_FILE"
    else
        echo "⚠ Konfigürasyon dosyası bulunamadı: $CONFIG_FILE"
        echo "  Önce kalibrasyon yapmanız gerekiyor."
        echo ""
        read -rp "  Otomatik kalibrasyon başlatılsın mı? (E/h): " yn
        if [ "$yn" != "h" ] && [ "$yn" != "H" ]; then
            auto_calibrate_and_start
        fi
    fi
}

start_console() {
    if [ -f "$CONFIG_FILE" ]; then
        echo ">>> Tracker başlatılıyor (Terminal)..."
        $PYTHON poker_tracker/main.py --console --config "$CONFIG_FILE"
    else
        echo "⚠ Konfigürasyon bulunamadı. Otomatik kalibrasyon yapılıyor..."
        $PYTHON poker_tracker/main.py --auto-calibrate
        [ -f "$CONFIG_FILE" ] && $PYTHON poker_tracker/main.py --console --config "$CONFIG_FILE"
    fi
}

calibrate_from_screenshot() {
    echo "  Ekran görüntüsü dosya yolunu girin:"
    read -rp "  > " img_path
    if [ -f "$img_path" ]; then
        $PYTHON poker_tracker/main.py --auto-calibrate --image "$img_path"
    else
        echo "HATA: Dosya bulunamadı: $img_path"
    fi
}

# ─── Komut satırı argümanları ───

case "${1:-menu}" in
    start)
        start_tracker
        ;;
    calibrate|auto)
        $PYTHON poker_tracker/main.py --auto-calibrate
        ;;
    manual)
        $PYTHON poker_tracker/main.py --calibrate
        ;;
    console)
        start_console
        ;;
    screenshot)
        if [ -n "$2" ]; then
            $PYTHON poker_tracker/main.py --auto-calibrate --image "$2"
        else
            calibrate_from_screenshot
        fi
        ;;
    menu|"")
        while true; do
            show_menu
            case $choice in
                1) auto_calibrate_and_start; break ;;
                2) start_tracker; break ;;
                3) start_console; break ;;
                4) $PYTHON poker_tracker/main.py --auto-calibrate ;;
                5) calibrate_from_screenshot ;;
                6) $PYTHON poker_tracker/main.py --calibrate ;;
                7) echo "Çıkış."; exit 0 ;;
                *) echo "Geçersiz seçim." ;;
            esac
            echo ""
            read -rp "Devam etmek için Enter'a basın..." _
        done
        ;;
    *)
        echo "Kullanım: $0 {start|calibrate|manual|console|screenshot [dosya]|menu}"
        exit 1
        ;;
esac
