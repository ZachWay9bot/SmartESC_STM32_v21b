# SmartESC G30 Gen1 – DRV126-Abgleich und Software-Freeze
Stand: 2026-10-24. Branch: `audit/vesc-g30-20261021`, Draft PR #23.
Status: **BMS-VESC-Tool-Port umgesetzt / IoT-IAP unverändert / HARDWARE-BENCH-PENDING**, kein hardwarequalifiziertes Fahr-Release.

**Verbindlicher neuer Stand, 24.10.2026:** IoT = USART1 PB6/PB7, original UART-IAP/Recovery; BMS = USART3 PB10/PB11, jetzt aktive VESC-Tool-Schnittstelle; gelbe Leitung = USART2 PA2, Ninebot-Dashboard. Neuester Softwarecommit `5341ebe5d0cddf888f3397cfe7c98b960379b344`, Build `SmartESC-G30-BENCH-278` ([GitHub Actions](https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/runs/40133329522)); Hosttests und Recovery-Audit für den aktuellen Branch weiterhin grün. Kein SmartESC-Flash oder echter VESC-Tool-Test bisher.

## Live-Update 24.10.2026 – G30 Gen1 angekommen

- Der jetzt angeschlossene Controller antwortete mit der originalen Identität
  `N4GEA1601C0001` und Versionsrohbytes `87 01`, d. h. DRV `0x0187` / 1.8.7,
  auf COM9 über den vorhandenen Ninebot-UART. Dies ist noch **keine** SmartESC-Firmware.
- Private RemoteLab-Steuerqueue `ZachWay9bot/xbot-remote-lab` #5 wurde neu eingerichtet.
  Der alte FO91-Kanal #1 ist archiviert/gesperrt. Agent v0.6.0 hat #5 erfolgreich
  per Ping bestätigt; ein alter FO-spezifischer Diagnoseaufruf erhielt von
  Stock keine nutzbare Antwort. Die Flash-/Motor-Permit-Session ist abgelaufen.
- **Aktuelle VESC-Tool-Zuordnung:** `VESC_USART_DMA=huart3` nutzt BMS USART3
  (TX PB10 / RX PB11), 115200 8N1. `APP_USART_DMA=huart2` bleibt die
  Ninebot-Halbduplex-Dashboard-Leitung PA2. Das bewährte IoT-IAP mit USART1
  PB6/PB7 bleibt davon getrennt. COM9 ist am IoT angeschlossen, nicht der BMS-Port.
- Die G30-Firmware antwortet als VESC-FW **5.03** (`defines.h`); die früheren
  Dokumentangaben zu 6.06 beziehen sich auf Serialisierer-/Hostannahmen, nicht
  auf eine nachgewiesene VESC-Tool-Live-Verbindung. Firmwareversionswechsel
  nicht als Schein-Kompatibilitätsfix vornehmen.
- Die aktive G30-Dispatchervariante implementiert bereits
  `COMM_DETECT_APPLY_ALL_FOC` (R/L/Flux, Konfigurationsspeicherung und
  16-Bit-Ergebnisantwort). Das ist **nur softwareseitig verifiziert**;
  noch keine vollständige VESC-Tool-Motor-Detection am echten Gen1.
- Nach dem Einstecken bestätigt der neue Agent noch **keinen** unabhängigen
  UART-IAP-Stock-Restore. Den bewährten Bootloader/IAP unverändert lassen.

### VESC-UART-Zuverlässigkeit – Quellkorrektur am 24.10.2026

Auf dem Entwicklungsbranch wurden ausschließlich die FreeRTOS-allokierten
VESC-Paketpuffer und das Fehlerverhalten des CLI-Tasks abgesichert. Wenn
`pvPortMalloc` NULL liefert, wird kein Nullpointer mehr dereferenziert,
und der UART-Task startet nicht mit unvollständigen Puffern. Bestehende
VESC-Frames auf dem erfolgreichen Pfad, Motorsteuerung und Ninebot-IAP
sind unverändert. Der echte `packet.c`-Test prüft beide OOM-Punkte.
Commit `fc6d7389bfcf8b086c70954ebfaa5491e98cfd31`:
[Host-CI](https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/runs/40130747458),
[STM32-Build](https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/runs/40130747569),
[Recovery-Audit](https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/runs/40130747514)
alle erfolgreich. **Keiner dieser Erfolge beweist elektrische Hardwaretauglichkeit.**

### Entscheidend: IoT-IAP beibehalten, Zielhardware-Rückweg vor Flash bestätigen

Im wirklich aktiven SmartESC-Source verwendet `common_files/src/g30_recovery_iap.c`
bei Frühstart `uart_init_rec()` **USART1 auf PB6/PB7** (AFIO-Remap);
`g30p/Src/main.c` und `common_files/inc/product.h` benutzen für die
gewöhnliche Stock-Dashboard-Eindrahtleitung dagegen **USART2/PA2**.

Der aktuell erfolgreiche Stock-Test `N4GEA1601C0001` / `0x0187` lief auf
**IoT/COM9**. Nach der expliziten Hardwarezuordnung ist dieser Weg tatsächlich
USART1 PB6/PB7 und damit derselbe UART, den die unveränderte SmartESC-
Frühstart-Recovery benutzt. Ein **unabhängiger Stock-IAP-Restore nach einem
komplett nichtstartenden SmartESC-Image** ist für die aktuelle Hardware
aber weiterhin nicht durch Live-Messung nachgewiesen.
Die gegenwärtige lokale Agent-Software v0.6.0 ist außerdem auf
`XBOTFOxx`-Applikationsversionen zugeschnitten, nicht auf eine echte
Stock-DRV1.8.7-basierte SmartESC-IAP-Sitzung.

**Daher kein automatisches Installieren des Bench-Drivers auf dem neuen
vergossenen Controller ohne Rückweg-Nachweis.** BMS PB10/PB11 ist der
getrennte VESC-Tool-Weg; ein PA2-Protokollmultiplexer ist weder erforderlich
noch beauftragt. IoT PB6/PB7 behält die bisherige Recovery-Konfiguration.

### Neuester G30-Bench-Kandidat: Coast-only und VESC-Allocator

SmartESC `b6fda7ec8830ca53a7ceb8d20bad55ea6c83ebaf`:
- In G30P führen Dashboard-Bremse und `COMM_SET_CURRENT_BRAKE`
  über `VescToSTM_set_brake_current_rel` / `VescToSTM_set_brake`
  nun zu 0 Stromvorgabe und PWM-Gates-off (Coast), **keine aktive
  Generator-/Rekuperationsbremse auf diesen Eingabepfaden**.
  Die Nicht-G30-Implementierung bleibt unverändert.
- `packet_init` und der G30 VESC-UART-Task sind gegen fehlgeschlagene
  FreeRTOS-Puffer-Allokationen abgesichert; bei fehlendem RAM wird der
  UART-Task nicht mit einem NULL-Paketpuffer gestartet.
- `COMM_DETECT_APPLY_ALL_FOC`, Sensorless-Rollstart, Timings,
  UART-Routing, IAP, Bootloader, App-Recovery, Linker und Flashlayout
  wurden nicht verändert.
- Für diesen exakten Commit [Hosttests](https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/runs/40131220129),
  [Bench ARM & verschlüsselter IAP-Kandidat](https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/runs/40131220136)
  und [UART-Recovery-Quellaudit](https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/runs/40131220146)
  sämtlich erfolgreich, **weiterhin kein realer Motor- oder Rückflashtest**.
- Das aktuelle Build-Artefakt heißt `SmartESC-G30-BENCH-278`. Es ist ein
  **nicht hardwarequalifizierter Kandidat**, kein freigegebenes Fahrimage.

**Am 24.10. erledigt:** Statt eines PA2-Multiplexers nutzt VESC Tool die
zugängliche BMS-UART-Leitung USART3 PB10/PB11. Im IoT/IAP-Pfad auf
USART1 PB6/PB7 und im Dashboard-Pfad USART2 PA2 wurde nichts geändert.
Die oben genannten früheren Kandidaten bleiben historische Referenzen;
aktuell ist ausschließlich Build `SmartESC-G30-BENCH-278` zu betrachten.



## Warum dieses Dokument existiert

Kein weiterer Kreislauf aus wiederholten Hosttests. Softwareentwicklung ist bis
auf konkrete, nachweislich notwendige Anpassungen am eintreffenden Controller
abgeschlossen. Der Controller ist am 24.10. eingetroffen; die Hardware-Identifikation lief erstmals, der SmartESC-Kandidat ist noch nicht geflasht. Das bestehende
UART-IAP und der Bootloader bleiben unverändert. Es gibt am Bench kein Dash;
SHU wird erst auf erneuten ausdrücklichen Auftrag zurückgebracht. Für den
aktuellen versiegelten Controller gibt es **keinen SWD/ST-Link-Zugang**.

Der Entwickler darf **nicht** aus dem erfolgreichen XBOT-FO76-Donor-Motorlauf
eine hardwarebestätigte Freigabe der aktuellen SmartESC-G30-BIN machen.

## 1. Referenz DRV126

Verglichen mit dem unveränderten DRV126-Anwendungsimage in
`itskenny0/ninebot-max-g30-firmware-patcher`, festem Commit
`f6f2c39941e6d10004727074bba016740c828cb5`,
Pfad `patcher/bins/DRV126.bin`.

**Tatsächlich erneut gelesen:** 30.076 Bytes, initial SP `0x20002B18`,
Reset-Handler `0x08001101` (App `0x08001000`). Als externen
Vergleich mit den früheren neun maschinennahen Fingerprints diente außerdem
die zuvor archivierte, am 09./17.10. geprüfte Original-Fulldump-Analyse
(`esc126_fulldump.bin`, 131.072 Bytes, SHA256
`9235b466a2f7449b8184560dbef9012d7c12b099e4076100a223ef68d204bb68`).
Das Original-Fulldump ist **nicht** mit dem SmartESC-Source-Tree verknüpft
und darf nicht ungeprüft zum Flashen eines anderen Controllers genutzt werden.

### Verifizierte Grundzuordnung

| Funktion | DRV126 / rekonstruierte Stockreferenz | SmartESC G30 Branch |
|---|---|---|
| Phase High-Side PWM | PA8/PA9/PA10 | PA8/PA9/PA10 |
| Phase Low-Side PWM | PB13/PB14/PB15 | PB13/PB14/PB15 |
| Strom-ADC | PA3/PA4/PA5 | ADC1/ADC2 mit Kanälen 3/4/5 |
| ADC1/2 sektorabhängig | 1/6: CH4/5; 2/3: CH3/5; 4/5: CH3/4 | gleiche Kanalpaare in `R3_2_ParamsM1` |
| Busspannung | PA1 | G30P `VBUS_ADC_CHANNEL=1` |
| Passive BEMF | PA6/PA7/PB1 | ADC6/ADC7/ADC9 |
| App-Basis | 0x08001000 | 0x08001000 |
| Update-Staging | ab 0x0800E800 | Anwendung endet vor 0x0800E800 |

Hier sind keine neuen hypothetischen Pin-/Strom-Mappings einzuführen.

### Wichtigster verbleibender PWM-Timing-Unterschied

| Merkmal | DRV126 Stock (rekonstruiert) | SmartESC aktueller Source |
|---|---|---|
| TIM1 Basisclock | 64 MHz, Prescaler 0 | 64 MHz, Prescaler 0 |
| Center-aligned ARR | **4000** | **2000** (16-kHz-PWM) |
| PWM-Takt | **ca. 8 kHz** | **ca. 16 kHz** |
| ADC-Trigger CH4 | PWM1, CCR4 ca. 3996 im Betriebsregime | PWM2 beim Init, dynamische CH4-Samplingpunkte durch MCSDK |
| BDTR.DTG | **0x40 / 64** | **25** (`SW_DEADTIME_NS=800`, `DEAD_TIME_COUNTS/2`) |
| TIM1 ClockDivider | noch NICHT bytegenau als CKD belegt | **DIV2** |
| Automatische Output-Freigabe | AOE=1 im Stock-Init | AOE deaktiviert |
| Break Input | BKE=0 in Stock-Referenz | Break deaktiviert |

**Deadtime ist nicht allein aus DTG-Zahlen vergleichbar.** Der effektive
Timer-Deadtime-Takt hängt von CKD ab. Für SmartESC: DTG=25 bei CKD=DIV2
und 64 MHz ergibt nominell **25 × 2 / 64 MHz ≈ 0,781 µs**. Die
Stock-DTG=64 ergibt ohne gesichertes Stock-CKD noch **keine**
belastbare elektrische Totzeit. Die frühere pauschale Behauptung
`TIM_BREAK_DISABLE` sei ein nur von SmartESC eingeführter Defekt,
war unzutreffend: Stock hatte im rekonstruierten Stand BKE=0.

Ein blindes Umschalten von 16 kHz auf 8 kHz, von PWM2 auf PWM1
oder von AOE=0 auf AOE=1 wäre eine **sicherheits- und
regelungsverhaltensrelevante Änderung**: MCSDK ADC-Triggersektoren,
Regelrate, Strom-PI, Observer, PWM-Off und Schaltzeitfenster hängen
zusammen. Keine solchen Änderungen in diesem Freeze.

## 2. Was aus echten Motorläufen folgt – und was nicht

Die XBOT-Donor-Plattform lief real: FO60 zwei 100-ms-Übernahmen,
FO69 vier volle 5-s-FOC-Läufe und ein kontrollierter CLAMP-Abbruch,
FO76 am 17.10. nach erfolgreichem IAP-Flash mit vollständigem
40.000/40.000-Tick-Takeover (max. 76 ADC-Strom-Counts, 0 Observer-Clamps).
Das war **echte Hardware** und wird nicht erneut in Frage gestellt.

Die tatsächlich FO76-geflashte Datei war 21.712 Byte,
SHA256 `35ceae5c635c66f667380fc8dd0777463aed5dde98014328d123be5965812554`.
Das spätere 21.728-Byte-FO76-Source-Artefakt mit derselben Identität
ist **nicht bytegleich**. Beide sind vom heutigen 52.108-Byte-
SmartESC-G30-Sourcebuild zu unterscheiden.

Originale Ergebnislogs:
- https://github.com/ZachWay9bot/xbot-remote-lab/issues/1#issuecomment-6243026704
- https://github.com/ZachWay9bot/xbot-remote-lab/issues/1#issuecomment-6243035433
- https://github.com/ZachWay9bot/DeltaESC-G30D/blob/main/MEASUREMENTS.md

## 3. Softwareabschluss: bestehende Belege, keine neue Dauertest-Schleife

Software für den aktuellen G30-Branch ist konsistent baubar; **57/57**
Host-/Protokolltests und der Recovery-Audit erfolgreich. Letzter
hardwareunabhängig vollständig erfolgreicher Build:
https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/runs/40033237826

Bench-Artefakte:
- `g30p.bin` – App 52.108 Byte, `0x08001000`
- `SmartESC_G30_BENCH_IAP_Driver.bin` – NinebotTEA 52.112 Byte
- Manifest, unabhängiger Datei-Identitätscheck, ELF/MAP, RAM-/Heap-Berichte

Der BENCH-Driver wird als **noch nicht hardwaregeprüfter Kandidat**
bezeichnet. Keine SHU-ZIP, kein stilles Flashen, keine IAP-Metadaten-Gates.

Aktuelle Architektur: 30 Magnetpole/15 Polpaare, G30-Rolling-
Start ab ungefähr 3 km/h, VESC Detect All verfügbar,
passive BEMF-Abtastung und Observer-Winkel mit Host-Simulation getestet.
Unveränderte Firmware-Einschränkungen:
- Erste echte FOC-ISR-Zeitreserve und Stromkalibrierung unbekannt.
- Kein Beweis für konkrete PWM-/Gate-Signalüberlappung oder die
  hardwareinterne Abschaltung des gelieferten Controllers.
- Die aktive G30-Dispatchervariante implementiert Detect All;
  Einzelbefehle R/L/Flux sind nicht separat freigeschaltet.
- `packet_init()` hat nach wie vor ungeprüfte Heap-Allokationen,
  `G30SL_CalcAvrgMecSpeedUnit()` nutzt nach Grace nicht das
  strengere `g30sl_core_run_valid()`. Für beide gilt:
  **unbeauftragte Motor-/UART-Designänderungen vermeiden**.
- SRAM linker-reserviert 20.088/20.480 Byte; 14 KiB
  FreeRTOS-Heap sind in `.bss`, nicht mit den 392 Byte
  unallokiertem SRAM zu verwechseln.

## 4. Verbindlicher Restablauf: nur reale neue Information zählt

1. **Controller eingetroffen:** Stock-Version, Hardware-ID und UART/IAP
   zuerst nur LESEN; keine ST-Link-Vorschläge.
2. **DRV126/Stock-Basis:** Phasen, ADC-Offset, Standstromsignale und
   PWM-Gate-Verhalten gegen die oben dokumentierten Referenzen
   verifizieren; bei Abweichung nur die betroffenen Konstanten/Module
   patchen, nicht die funktionierende Architektur neu beginnen.
3. **UART-IAP:** ursprünglichen FO76-Weg als Prozessreferenz nutzen,
   Bootloader/Flashlayout/IAP/Recovery unverändert lassen.
4. **Motor:** erst an strombegrenzter Versorgung, freiem Rad und
   festgelegter begrenzter Ausgangsleistung Detect All,
   Stromvorzeichen, Flux, Rotor-/Observerwinkel und FOC-Übernahme
   messen. Eine Schutzfunktion muss real funktionieren,
   nicht nur in Hosttests.
5. **Danach** nur konkrete Messergebnisfehler korrigieren;
   kein weiteres pauschales Regressions-/Umbaurad.

Diese Schritte sind keine Forderung nach einer weiteren
Softwaretestserie. Sie sind die **physikalische Abschlussprüfung**,
die bei fehlender Hardware schlicht noch nicht ausgeführt werden konnte.

## 5. Änderungsprinzip / Freeze

- **Keine Änderung** an dieser Quelle nur zur „Verbesserung“ von
  Bootloader/IAP/Recovery/SHU, GPIO-Motorfreigabe oder Schutzlocks.
- Stock-Abweichungen oben sind Review-Punkte, keine pauschale
  Freigabe, das Verhalten umzuschalten. Nutzen, Nachteile, Risiko,
  unverändert lassen und ausdrückliche Nutzerfreigabe beachten.
- Bis neuer realer Hardwareinformation eintrifft, bleibt
  dieser Branch **Software-Freeze**, nicht Straßenfahrfreigabe.
