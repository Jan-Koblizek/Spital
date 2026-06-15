# Spital - pruvodce konfiguraci

Tento dokument je pro upravy obsahu escape roomu bez zasahu do jadra programu.

Bezna prace se dela hlavne v techto mistech:

- `event_configs/*.json` - MQTT topicy, payloady, nazvy a tlacitka ve frontendu
- `device_state_configs/*.json` - ocekavane stavy zarizeni
- `src/locations.py` - chovani mistnosti a prechody mezi nimi

## Konfigurace udalosti

Kazdy soubor v `event_configs/` popisuje udalosti pro jednu lokaci.

```json
{
  "location": "tricet_valka",
  "events": [
    {
      "id": "tricet_valka_tlacitko1",
      "name": "Prvni Tlacitko",
      "topic": "spital/30_valka/tlacitko1",
      "description": "Dite zmacklo tlacitko",
      "payload": "1",
      "condition": "1"
    }
  ]
}
```

Polozky:

- `location`: musi odpovidat `config_id` tridy lokace.
- `id`: unikatni identifikator udalosti pouzivany v `locations.py`.
- `name`: zobrazuje se ve frontendu.
- `topic`: MQTT topic.
- `description`: zobrazuje se ve frontendu.
- `payload`: hodnota odeslana pri spusteni udalosti z kodu nebo frontendu.
- `condition`: volitelna podminka pro prichozi payload.
- `incoming`: volitelne; `false` znamena, ze udalost lze spustit z kodu nebo frontendu, ale prichozi MQTT zprava ji nespusti.

Jedna udalost muze odeslat i vice MQTT zprav. `topic` muze byt jeden topic nebo seznam topicu. `payload` muze byt jedna hodnota nebo seznam dvojic `[payload, zpozdeni_v_sekundach]`.

Pokud je pocet topicu stejny jako pocet payloadu, posle se kazdy payload na odpovidajici topic:

```json
{
  "id": "svetla_start",
  "name": "Zapni svetla",
  "topic": [
    "spital/svetlo/1",
    "spital/svetlo/2"
  ],
  "description": "Zapne dve svetla",
  "payload": [
    ["1", 0],
    ["1", 0.5]
  ]
}
```

Pokud se pocty neshoduji, vsechny payloady se poslou na prvni topic. To se hodi pro sekvenci zprav do jednoho zarizeni:

```json
{
  "id": "audio_sequence",
  "name": "Audio sekvence",
  "topic": "spital/audio/1",
  "description": "Spusti vice audio prikazu",
  "payload": [
    ["intro.mp3", 0],
    ["loop.mp3", 12]
  ]
}
```

Zpozdeni se pocita od prvni zpravy. Prvni zprava ma obvykle zpozdeni `0`.

Priklady podminek:

```json
"condition": "1"
```

```json
"condition": [10, 20]
```

Jedna hodnota znamena presnou shodu. Dvouprvkove pole znamena, ze prichozi payload musi byt cislo v danem rozsahu vcetne krajnich hodnot.

Duplicitni topicy jsou povolene. Pokud stejny topic pouziva vice udalosti, runtime vybere prvni udalost, ktera:

- patri do aktualni lokace
- splnuje svoji `condition`

## Kod lokaci

Logika mistnosti je v `src/locations.py`.

Zacatek a konec tour jsou zamerne viditelne v `src/main.py`:

```python
START_EVENT_ID = StartEvents.INIT
START_LOCATION = Start
END_EVENT_IDS = {
    TricetValkaEvents.NEXT,
}
```

`START_EVENT_ID` urcuje udalost, ktera vytvori novy runtime. `START_LOCATION` urcuje prvni lokaci. `END_EVENT_IDS` jsou ukoncovaci udalosti, ktere se bezne neschovavaji do logiky frontendu jako normalni tlacitka lokace.

Kazda lokace by mela mit:

```python
class TricetValka(Location):
    name = "Tricetileta Valka"
    config_id = "tricet_valka"
```

`config_id` propojuje tridu s odpovidajici konfiguraci v `event_configs/*.json`.

`name` je nazev lokace, ktery se zobrazuje ve frontendu.

Pro id udalosti pouzivejte enumy:

```python
class TricetValkaEvents(str, Enum):
    TLACITKO1 = "tricet_valka_tlacitko1"
    NEXT = "tricet_next"
```

Na udalosti se reaguje v metode `process_event`:

```python
def process_event(self, event_id, payload, send_event):
    if event_id == TricetValkaEvents.TLACITKO1:
        send_event(TricetValkaEvents.NEXT)

    if event_id == TricetValkaEvents.NEXT:
        return self.change_location(Adolf(), send_event)

    return self
```

Uzitecne pomocne funkce:

- `send_event(TricetValkaEvents.MP3)`: odesle nakonfigurovanou udalost podle id z enumu.
- `Timer(seconds, lambda: send_event(TricetValkaEvents.VIDEO)).start()`: odesle udalost se zpozdenim.
- `DeviceStateChecks.check(lambda: send_event(StartEvents.KONTROLA))`: pozada zarizeni o stav, zkontroluje odpovedi a vrati `True` nebo `False`.
- `return self.change_location(OtherLocation(), send_event)`: prejde do jine lokace.

Lokace s `config_id = None` je finalni. Kdyz do ni runtime vstoupi, skonci a zmizi z frontendu.

## Pocatecni stav zarizeni

Konfigurace stavu zarizeni je v `device_state_configs/*.json`.

Soubor je JSON objekt, kde klic je topic a hodnota je ocekavany payload:

```json
{
  "spital/device/door/state": "closed",
  "spital/device/light/value": [10, 20]
}
```

Vyklad:

- `"closed"`: payload se musi presne rovnat `closed`
- `[10, 20]`: payload musi byt cislo od 10 do 20 vcetne

Kdyz se spusti kontrola stavu:

1. Lokace odesle udalost, ktera pozada zarizeni o stav.
2. Zarizeni maji poslat svuj aktualni stav.
3. Aplikace ceka maximalne 2 sekundy.
4. Pokud dorazi vsechny nakonfigurovane topicy a hodnoty sedi, kontrola projde.

Udalost `kontrola` je v `event_configs/start.json`. Pro pozadavek na stav je vhodne ji nastavit jako odchozi-only, aby se vlastni MQTT publish nevratil zpet jako dalsi runtime udalost:

```json
{
  "id": "kontrola",
  "name": "Kontrola pred zahajenim.",
  "topic": "spital/state/request",
  "description": "Priprava na novou tour.",
  "payload": "1",
  "incoming": false
}
```

Kontrolu lze zavolat z lokace pres statickou tridu:

```python
from device_state import DeviceStateChecks

if DeviceStateChecks.check(lambda: send_event(StartEvents.KONTROLA)):
    send_event(StartEvents.START)
```

`DeviceStateChecks.check(...)` nejdriv zacne poslouchat odpovedi, potom zavola predanou funkci a nakonec ceka na nakonfigurovane stavy. Samotna kontrola nevi, jakou udalost lokace pouziva pro dotaz na zarizeni.

## Frontend

Spustte aplikaci a otevrene URL, ktere se vypise do konzole.

Adresa frontendu se nastavuje v `.env`:

```env
FRONTEND_HOST=127.0.0.1
FRONTEND_PORT=8000
```

Frontend umoznuje:

- spustit runtime
- spoustet dostupne udalosti pro kazdy runtime
- zabit runtime
- znovu nacist konfigurace udalosti bez restartu aplikace

Po zmene `event_configs/*.json` pouzijte tlacitko `Reload events`.

Konfigurace stavu zarizeni se aktualne nacita pri startu aplikace.

## Pravidla pro upravy

- Kazde `id` udalosti musi byt unikatni.
- `config_id` lokace musi odpovidat `location` v konfiguraci udalosti.
- Nemente id udalosti, pokud se pouzivaji v `locations.py`.
- MQTT payloady prichazeji jako text.
- `condition` pouzivejte pro jednoduche kontroly payloadu; slozitejsi logiku dejte do Python kodu lokace.
- Pokud ma byt udalost videt ve frontendu, dejte ji do konfigurace aktualni lokace.

## Spusteni

Instalace zavislosti:

```powershell
pip install -r requirements.txt
```

Spusteni aplikace:

```powershell
python src/main.py
```

Frontend URL se vypise do konzole.
