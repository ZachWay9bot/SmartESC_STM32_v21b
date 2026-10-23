# SmartESC G30 identical – Softwarepakete vor Eintreffen des Controllers
Stand: 2026-10-24 · Branch `audit/vesc-g30-20261021` · Draft-PR #23

## Geltungsbereich

**Noch kein neuer Controller vorhanden.** Dies ist eine softwarebasierte
Entwicklungs-/Buildprüfung und weder ein Motorlaufnachweis noch eine
Flash- oder Fahrfreigabe. Am Prüfstand existiert derzeit **kein Dashboard**.
SHU-Unterstützung ist deshalb aus den aktiven Builds/Tag-Releases entfernt
und wird ausschließlich nach erneuter expliziter Beauftragung integriert.

**Nicht geändert:** Bootloader, STM32-Flashlayout, UART-IAP-Kommandos,
Recovery-/Wiederherstellungsablauf, Motor-/FOC-Laufzeitentscheidungen,
Regelparameter, Bremse/Recup und Dashboard-Betriebslogik.

## Abgeschlossene Softwarepakete

### Paket 1 – echter portabler C-Observer, Grenzfälle

Neue Testdatei: `tools/tests/test_g30_core_edge_cases.py`.

- CPU-Timerüberlauf `uint32_t` bei laufender BEMF-Sektorfolge.
- Drehzahlschwelle unter/über nominell 3 km/h (Gen1: 15 Polpaare).
- Richtungsumkehr nach bereits erlangtem Lock, ohne den alten Lock
  über einen Richtungswechsel hinweg weiterzuverwenden.
- Wiederholte Abtastung desselben Sektors (kein zusätzliches Flankenereignis).
- BEMF-Abbruch und Aufbau eines neuen Locks ausschließlich mit neuen Flanken.
- Leere Flux-Konfiguration: keine initiale Observer-Freigabe;
  Nullwerte aus `set_motor` ersetzen keine gültigen Kalibrierungswerte.

Bereits bestehende Tests decken die Seed-Phasenlage über sechs Sektoren,
Vorwärts-/Rückwärtsrotation, unplausible Beobachterwerte, FOC-Strompfad,
Rolling-Lock und ADC-Anbindung ab. Alles synthetisch; die reale
G30-Motorphasenlage bleibt ungeprüft.

### Paket 2 – UART-IAP-Benchformat ohne SHU

Neue Datei: `tools/tests/test_g30_bench_iap_contract.py`.

- Validierung von SP/Resetvektor und Anwendungsadressfenster
  `0x08001000..0x0800E7FF`; Bootloaderbereich als App-Reset verboten.
- Klartext-/verschlüsselte Staging-Limits, inklusive TEA-Checksum-Padding.
- Unveränderte NinebotTEA-Erzeugung und Binär-/Manifest-SHA256.
- CLI darf Eingabe-BIN nicht überschreiben und erzeugt **keine SHU-ZIP**.

### Paket 3 – aktiv verwendeter G30-VESC-Dispatcher / Detect All

Neue Datei: `tools/tests/test_g30_vesc_detect_regression.py`.

- Erreichbarkeit des **kompakten G30-Dispatchers**, unabhängig vom
  Legacy-Zweig.
- Paketlängen für Strom-/Brems-Kommandos und selective-values-Mask.
- Detect-All-Worker-Start, Ablehnung während laufendem Detect,
  Abort per `COMM_APP_DISABLE_OUTPUT`, und Fehlerantwort bei
  fehlgeschlagenem Task-Start.
- Begrenzte R/L/Flux-Werte, Parameter-Speicherung vor Erfolgsmeldung,
  Rückgabe von Messkonfiguration nur nach erfolgreichem Store.

**Bekannte Funktionseinschränkung:** G30 implementiert
`COMM_DETECT_APPLY_ALL_FOC`, nicht die individuellen
`COMM_DETECT_MOTOR_R_L` / `COMM_DETECT_MOTOR_FLUX_LINKAGE_OPENLOOP`
im kompakten G30-Dispatcher. Einzelne manuelle VESC-Tool-Detektionsbuttons
dürfen deshalb nicht als bestätigt dargestellt werden. Eine Erweiterung
ist eine Laufzeitverhaltensänderung und braucht separate Besprechung.

### Paket 4 – Quellcode-Audit FreeRTOS-Heap und Task-Starts

Neue Dateien: `tools/audit_g30_heap_paths.py`,
`tools/tests/test_g30_heap_path_audit.py`.

Bericht `g30-heap-audit.json` wird beim Bench-Build zusammen mit
`g30-ram-audit.json` hochgeladen.

**Bekannte ungeprüfte Pfade im aktuellen Quellcode:**

1. `packet_init()`: `pvPortMalloc(PACKET_STATE_t)` wird direkt
   mit `memset` dereferenziert; die anschließende RX-Pufferallokation
   ist ebenfalls ungeprüft.
2. `task_app()`: der Dashboard-UART-DMA-RX-Puffer wird ohne Nullprüfung
   an HAL übergeben. Auf dem gegenwärtigen Prüfstand fehlt das Dashboard,
   der Sourcepfad ist trotzdem vorhanden.
3. `task_app_init()`: `xTaskCreate`-Rückgabewert wird nicht geprüft.

Die Konfigurations-Sendepuffer und der G30-Detect-All-Taskstart haben
bereits Quellcodeprüfungen auf Allokations-/Taskstartfehler.

**Wichtig:** Dies ist eine bewusst begrenzte statische Inventur
bekannter Codepfade, keine vollständige Memory-Safety-Analyse.
Aus dem ELF-Link ist das reale FreeRTOS-Laufzeitminimum **nicht**
ableitbar. SRAM 20.480 Byte, bis Reservierungsende 20.088 Byte,
392 Byte außerhalb linker-reservierter Sektionen; FreeRTOS `heap_4`
reserviert 14.336 Byte **innerhalb von .bss**. Die 392 Byte sind
nicht der verfügbare FreeRTOS-Heap.

**Keine Behebung auf Verdacht** in den IAP-relevanten UART-/Paketpfaden.
Fehlerursache, Risiken und Alternative unverändert lassen vor einem
eventuellen Laufzeitpatch separat entscheiden.

### Paket 5 – Offline-Konsistenz vor dem ersten Flash

Neue Dateien: `tools/verify_g30_bench_artifacts.py`,
`tools/tests/test_g30_bench_verification.py`.

Die CI prüft jetzt nach Erstellen des Bench-Images und vor dem
Artefakt-Upload, ob diese **exakten** drei Dateien zusammenpassen:

- `g30p.bin`: App-Vektor und Speichergrenzen.
- `SmartESC_G30_BENCH_IAP_Driver.bin`: exakt die NinebotTEA-
  Verschlüsselung der aktuellen BIN, inklusive Checksum/Padding.
- `SmartESC_G30_BENCH_MANIFEST.json`: exakte Längen, Hashes und Vektoren.

Die Gegenprüfung schreibt `SmartESC_G30_BENCH_VERIFY.json`.
Manipulierte, vertauschte, abgeschnittene Dateien oder falsche
Manifeste werden in Negativtests abgelehnt. Encoder und Verifier
verwenden dieselbe NinebotTEA-Implementierung: Das stellt
**Artefaktidentität, nicht unabhängige kryptografische
Kompatibilität zur FO76-Hardware** fest.

Manueller Read-only-Test, von Repository-Root mit entpacktem CI-Artefakt:

```powershell
py tools/verify_g30_bench_artifacts.py g30p.bin SmartESC_G30_BENCH_IAP_Driver.bin SmartESC_G30_BENCH_MANIFEST.json
```

Diese Prüfung hat **keinen seriellen Zugriff und kann nichts flashen**.

## Automatische Regressionen

- 56/56 G30-Hosttests am Pakete-5-Stand erfolgreich:
  https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/runs/40032932072
- Anti-Lockout/Recovery-Quellcodecheck:
  https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/runs/40032932112
- Bench-Build (ohne SHU) und aktuelle Buildartefakte:
  https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/runs/40032932134

## Vom Controller abhängige letzte Schritte

1. Ankommenden Controller und vorhandene Stock-DRV-Version **nur lesend**
   identifizieren; kein ST-LINK/SWD an dieser vergossenen Hardware.
2. UART-Bench-IAP-Prozess an erfolgreichem FO76-Ablauf vergleichen,
   ohne neue Restore-Sperren oder ungefragte Flash-Versuche.
3. **Erst nach abgestimmter Bench-Freigabe:** eigentliche neue Firmware
   laden und ADC-Stromoffsets, drei BEMF-Phasen und Drehrichtung messen.
4. Detect All: R/L/Flux, Speichern, Neustart, wiederholtes Auslesen.
5. Erst dann niedriger FOC-Motorlauf, Beobachterwinkel/ERPM unter
   strombegrenzter Versorgung und freiem Rad prüfen.
6. Tatsächliche FreeRTOS-Heap- und Stack-High-Watermarks unter
   UART/Detect-All-Last sowie Zeitreserven der PWM/FOC-ISR messen.

Die frühen FO76-Flash- und Motorlauftests sind historische
Hardwareerfahrung, **kein** Hardwaretest der heutigen SmartESC-BIN.
