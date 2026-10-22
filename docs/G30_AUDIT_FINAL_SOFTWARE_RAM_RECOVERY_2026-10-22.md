# SmartESC G30 identical: Abschluss Software-Audit A/B/C
Datum: 2026-10-22 · Branch: `audit/vesc-g30-20261021` · Draft PR #23

> **Keine Fahrfreigabe oder Flash-Freigabe.** Sämtliche neuen Funktionen sind **read-only Build-Audits, Tests oder Dokumentation**. Kein Eingriff in Bootloader, IAP, Recovery, SHU-Freigaberegel, Linkerlayout, ADC, PWM, FOC-Schalter oder Motorzustandslogik.

## A. FOC- und Winkelprüfung

- Die bereits getesteten drei Stromphasen, Clarke/Park, Strom-PI und die Übergabe in `G30SL_ObserverStep` sind quellcodeseitig verdrahtet.
- Zusätzlicher Test im echten portablen `g30_sensorless_core.c`: Abgleich des **Start-Beobachterwinkels gegen den BEMF-Kommutierungswinkel in allen sechs Sektoren bei Vorwärts- und Rückwärtsrichtung**. Der Test prüft auch 16-Bit-Winkelüberläufe (wrap-around).
- Vorhandene dynamische Tests überprüfen einen vorwärts/rückwärts wandernden Fluss und die Erkennung unplausibler Beobachterwerte; dies **ist keine real gemessene Phase-, Strom- oder Rotorposition**.
- Konfiguration Gen1: **15 Polpaare, 30 Magnetpole (`si_motor_poles=30`)**. Keine Änderung.
- **Ohne neue Freigabe nicht geändert:** `G30SL_CalcAvrgMecSpeedUnit` bewertet nach `active_grace` derzeit `observer_seeded && observer_bad < 20`; der Kern hat zusätzlich ein noch nicht dort benutztes strengeres `g30sl_core_run_valid` mit `observer_valid`. Eine Aktivierung verändert Fehler-/Motorabschaltverhalten und muss vorab mit Nutzen, Risiken und unveränderter Alternative entschieden werden.
- Ebenfalls noch hardwareoffen: realer Stromshunt-Gain/Offsets, BEMF-Spannungsskalierung, Motorphasenvorzeichen, Flux-Korrekturfaktor 2,0, harte Timingreserve der FOC-ISR.

## B. SRAM-/Heap-/Stackbudget

### Gemessen am **gelinkten G30P ELF** (nicht geschätzt)

Die read-only Analyse `tools/audit_g30_ram.py` liest ELF32-ARM-Sektionen einschließlich `NOBITS`-Reservierungen und schreibt nach erfolgreichem Linken einen JSON-Bericht. Sie läuft nun im GitHub-Workflow **vor** der bewusst blockierten SHU-Verpackung.

- **Physisches SRAM-Fenster:** 20.480 Byte ab `0x20000000`.
- **Bis zum Ende der belegten ELF-Sektionen einschließlich Start-Heap/-Stack-Reservierungen:** 20.088 Byte.
- **Außerhalb der belegten ELF-Sektionen:** 392 Byte (Compiler-/Linker-Alignment erklärt Unterschiede zu einer naiven Addierung der `size`-Ausgabe).
- **FreeRTOS heap_4 (statisch in `.bss` reserviert):** 14.336 Byte (`HEAP_SIZE_KB=14`). **392 Byte sind ausdrücklich nicht das freie FreeRTOS-Heap!**
- **Linker-Reservierung:** `_Min_Heap_Size=0x100` (libc/Newlib) und `_Min_Stack_Size=0x400` (MSP). Diese sind bereits Teil der ELF-SRAM-Belegung, nicht zusätzlich zu addieren.
- **Freier RTOS-Heap und Stack-High-Watermarks:** ohne ausgeführte Firmware **unbekannt**. Es gibt keine belastbare Behauptung, dass unter voller UART-, Dashboard- und Detect-All-Last noch genügend Heap und Stack frei sind.
- **Statische Budgetträger:** VESC-UART-RX-DMA 512 Byte; Stock-Dash-DMA 128 Byte; VESC-Paketpuffer `PACKET_MAX_PL_LEN+8=520` Byte; Task-Stacks `tskCLI=320`, `APP-ADC=128`, `tskLED=128`, `g30det=320` **FreeRTOS-Worte** zu je 4 Byte; zusätzlich Scheduler-/Timer-Tasks, TCB, Timer, APPCONF-/MCCONF-Buffer und Heap-Overhead.
- **Befund/Restrisiko:** `packet_init()` in `common_files/src/packet.c` dereferenziert das Ergebnis von `pvPortMalloc(sizeof(PACKET_STATE_t))` vor einem Null-Check und prüft die zweite Allokation des 520-Byte-RX-Puffers nicht. Ebenso gibt es Tasks, die UART-RX-Puffer-/Task-Erzeugungsfehler nicht ausreichend behandeln. Das ist relevant bei Heapdruck. Ein Eingriff in den laufenden VESC/UART-Kommunikationspfad könnte gerade bei einem vergossenen Controller den IAP-Zugang gefährden. **Daher nicht stillschweigend verändert; vor nächster Flash-Freigabe gezielt auf separater Hardware und mit validiertem Recovery-Pfad testen.**
- Für echte Grenzwerte beim Bench-Test die bereits von FreeRTOS unterstützten `xPortGetFreeHeapSize()` und `uxTaskGetStackHighWaterMark()` auslesen oder in einen **separat freigegebenen** Diagnoseschritt integrieren.

CI-Beispiel: [G30 SRAM-Audit im Build 39712030835](https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/runs/39712030835); zuerst fehlgeschlagene JSON-Ausgabe in root-eigenem Docker-Unterordner inzwischen auf beschreibbares Repository-Root umgestellt. Der Audit erzeugt **nur JSON, keine flashbaren Images**.

## C. IAP/SHU / unabhängiger UART-Stock-Restore

Quellpfad `tools/recovery/release_qualification.py` wurde **nicht geändert**. Die vorhandene Releasebedingung `--release` verlangt:

1. **Board-Profil:** `G30_STM32F103_3CAP`, realer Flashgeometrie-Nachweis `128K_VERIFIED`, SHA256 des tatsächlichen Bootloaders.
2. **Exaktes Image:** SHA256 des Kandidaten, für den der Restore nachgewiesen wurde.
3. **Echte originale Stock-DRV-Wiederherstellung:** richtiger DRV-Image-SHA256, dazu unverfälschtes Restore-Log mit SHA256 sowie der tatsächliche Nachweis eines **unabhängigen Rettungszugangs**, nicht lediglich die 3-s-Recovery-Funktion innerhalb unserer ersetzbaren App.
4. **Prüfdetails:** UART-Verdrahtung, echter Entry-Point, Prüfer/Zeuge und Datum.

Die Vorlage `docs/G30_UART_RESTORE_EVIDENCE_TEMPLATE.json` ist **absichtlich nicht qualifiziert** (Nullwerte und `independent_rescue=false`, `actual_restore_to_stock=false`). Die ergänzten Negativtests bestätigen, dass fehlende Felder, ein abweichender Kandidatenhash, falsche Flashgeometrie oder fehlender Restore die Freigabe nicht erfüllen.

Wichtig: Die statische Releaseprüfung ist nur ein Softwarefilter und **kein unabhängig verifizierendes Beweissystem**. Selbst formal valide JSON-Felder ersetzen die physische Rückflashprüfung nicht. Keine booleschen Werte oder Hashes erfinden.

**Lesender Vorabtest, niemals flashen:**
```powershell
py tools/recovery/release_qualification.py --release --evidence docs/G30_UART_RESTORE_EVIDENCE_TEMPLATE.json --image PFAD_ZUR_GENAUEN_KANDIDATEN_BIN
```
Dieser Test **muss blockieren**, solange die unabhängige Rückflashprüfung fehlt. Er greift weder auf UART noch auf Flash zu.

Die im Repository bereits vorhandenen Dateien unter `firmware/v0.8.7/` sind **Altartefakte**, keine geprüfte BIN dieses Branch-Commits. **Nicht als aktuelle SmartESC-Firmware ausgeben oder flashen.**

### Noch vom echten Controller abhängig

- Eigenständiges UART-Stock-Restore (vor jedem neuen Flash) unabhängig belegen, inklusive Geometrie.
- Ruhestrom-/Offsetmessung (ADC1/2), drei Motorphasen und Polarität prüfen.
- Detect All: R, L, Flux und Rücklesen nach Neustart.
- Frei drehendes Rad, strombegrenztes Labornetzteil, Anschieben bis ca. 3 km/h, danach niedriger Gasbefehl. Beobachter- und Stromwerte erfassen.
- Verifikation von Dashboard, Bremspriorität, Timeout, Lastwechsel, Abort und Stack/Heap-Minima. Keine Straßenfahrt ohne nachgewiesenen sicheren Prüfstandlauf.
