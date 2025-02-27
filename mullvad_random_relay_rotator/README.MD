# Mullvad Random Relay Rotator

Mullvad Random Relay Rotator to skrypt służący do zarządzania połączeniem VPN Mullvad. Skrypt cyklicznie zmienia serwer, co pomaga w zwiększeniu anonimowości oraz bezpieczeństwa połączenia.

## Wymagania

- System operacyjny wspierający bash (Linux, macOS itp.)
- Zainstalowany Mullvad VPN CLI
- Uprawnienia do wykonywania skryptu (np. chmod +x)

## Instalacja

1. Skopiuj plik `mullvad_random_relay_rotator.sh` do wybranej lokalizacji.
2. Nadaj skryptowi uprawnienia do wykonania:
chmod +x mullvad_random_relay_rotator.sh

## Użycie

Uruchom skrypt, podając jako argument interwał restartu (w sekundach):

```
./mullvad_random_relay_rotator.sh <restart_interval_seconds>
```

## Przykład
Aby zmieniać serwer co 10 minut (600 sekund):

```
./mullvad_random_relay_rotator.sh 600
```

## Działanie

1. Rozłączenie bieżącego połączenia VPN.
2. Losowy wybór serwera Mullvad.
3. Ponowne połączenie z VPN.
4. Odliczanie do następnej zmiany serwera.