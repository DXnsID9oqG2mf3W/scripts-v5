#!/bin/bash

# Sprawdzenie, czy podano argument określający interwał restartu
if [ $# -ne 1 ]; then
    echo "Usage: $0 <restart_interval_seconds>"
    exit 1
fi

# Walidacja, czy argument jest dodatnią liczbą całkowitą
if ! [[ "$1" =~ ^[0-9]+$ ]]; then
    echo "Error: The restart interval must be a positive integer."
    exit 1
fi

RESTART_INTERVAL="$1"

# Ustawienie nazwy pliku logu (zakłada, że skrypt ma rozszerzenie, np. .sh)
LOGFILE="${0%.*}.log"

# Definicja kolorów
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m' # Brak koloru

# Funkcja logująca wiadomość z aktualnym timestampem, zarówno na terminal, jak i do pliku
log() {
    local color="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    # Wyświetlenie kolorowej wiadomości na terminalu
    echo -e "${color}${timestamp} - ${message}${NC}"
    # Zapisanie wiadomości do pliku logu
    echo "${timestamp} - ${message}" >> "$LOGFILE"
}

# Funkcja wykonująca odliczanie na tej samej linii z użyciem koloru MAGENTA
countdown() {
    local seconds=$1
    while [ $seconds -gt 0 ]; do
        # Obliczenie godzin, minut i sekund
        local hours=$((seconds / 3600))
        local minutes=$(((seconds % 3600) / 60))
        local secs=$((seconds % 60))
        # Wyświetlenie odliczania w jednej linii (\r powoduje powrót kursora na początek linii)
        printf "\r${MAGENTA}Remaining: %02d:%02d:%02d${NC}" "$hours" "$minutes" "$secs"
        sleep 1
        seconds=$((seconds - 1))
    done
    # Przejście do nowej linii po zakończeniu odliczania
    printf "\n"
}

while true; do
    log "${RED}" "Disconnecting current connection..."
    mullvad disconnect
    sleep 1  # Krótkie oczekiwanie, aby upewnić się, że połączenie zostało rozłączone

    log "${GREEN}" "Selecting random server..."
    mullvad relay set location any
    sleep 1  # Pauza na ustawienie nowego serwera

    log "${YELLOW}" "Reconnecting..."
    mullvad connect

    log "${BLUE}" "Waiting ${RESTART_INTERVAL} seconds before next server change..."
    countdown "$RESTART_INTERVAL"
done
