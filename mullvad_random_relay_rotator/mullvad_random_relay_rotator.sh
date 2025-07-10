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

# Tu edytuj listę wykluczonych krajów. Wpisuj po angielsku, jak w JSON Mullvada (np. "United States")
EXCLUDED_COUNTRIES=("Serbia" "UK" "Canada" "Nigeria" "Estonia" "Malaysia" "USA" "Mexico" "China" "Singapore" "Australia" "Japan" "Hong Kong" "Russia" "Turkey" "Brazil" "India")

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

get_current_country() {
    mullvad status --json | jq -r '.details.location.country'
}

is_country_excluded() {
    local country="$1"
    for excluded in "${EXCLUDED_COUNTRIES[@]}"; do
        if [[ "$country" == "$excluded" ]]; then
            return 0
        fi
    done
    return 1
}

while true; do
    log "${RED}" "Disconnecting current connection..."
    mullvad disconnect
    sleep 1  # Krótkie oczekiwanie, aby upewnić się, że połączenie zostało rozłączone

    # Próbuj do skutku wybrać dozwolony kraj
    while true; do
        log "${GREEN}" "Selecting random server..."
        mullvad relay set location any
        sleep 1

        log "${YELLOW}" "Reconnecting..."
        mullvad connect
        sleep 3  # Daj chwilę na nawiązanie połączenia

        country=$(get_current_country)
        if [ -z "$country" ]; then
            log "${RED}" "Could not get country info from Mullvad. Retrying..."
            mullvad disconnect
            sleep 2
            continue
        fi

        log "${BLUE}" "Connected to country: $country"
        if is_country_excluded "$country"; then
            log "${RED}" "Country '$country' is excluded. Rotating again..."
            mullvad disconnect
            sleep 2
        else
            break
        fi
    done

    log "${BLUE}" "Waiting ${RESTART_INTERVAL} seconds before next server change..."
    countdown "$RESTART_INTERVAL"
done
