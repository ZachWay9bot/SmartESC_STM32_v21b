# SmartESC G30 identical: Punkt 3.3 + Punkt 4, Softwareprüfung
Stand: 22.10.2026 · Arbeitsbranch: `audit/vesc-g30-20261021` · PR #23 (Draft)

## Ergebnis

**Erledigt, softwareseitig:**
1. Strommessung nachvollzogen: ADC1/ADC2 mit linksbündiger Datenablage, G30-Phasenkanäle 3/4/5, F1xx-R3_2-Rekonstruktion der drei Phasen und Übergabe über Clarke/Park, Strom-PI, inverse Park-Transformation und PWM.
2. **Bestätigter Quellcodefehler behoben:** In `R3_2_GetPhaseCurrents()` wurde bei der vorhandenen Überstromprüfung `Ia` doppelt und `Ib` gar nicht geprüft. Der zweite Vergleich verwendet jetzt `Ib`. Beispiel mit dreiphasiger Summe 0: `Ia=-50, Ib=100, Ic=-50` bei Grenzwert 80 muss auslösen. Kein Grenzwert und kein neuer Schutzmechanismus geändert.
3. **Bestätigter Parserfehler behoben:** G30 `COMM_SET_MCCONF` akzeptierte bereits 4 Byte, der vorhandene generierte Decoder liest jedoch genau **484 Byte**. G30 verlangt nun die vollständige 484-Byte-Nutzlast **vor** jedem Decoderzugriff. Der Serialisierer und Deserialisierer sind statisch auf 484 Byte abgeglichen. `COMM_SET_APPCONF` bleibt wie zuvor auf **476 Byte** begrenzt.
4. Beim G30-Motorkonfigurations-Schreibkommando folgt das VESC-ACK nun **nur auf einen erfolgreichen Rückgabewert des bestehenden Speicherschreibers**. Keine Änderung an Flash-Adressen, Flash-Schreibfunktion, IAP oder Recovery.
5. Bestehende Gas-/Bremspriorität im Stock-Dashboardpfad anhand des tatsächlichen ADC-Timercallbacks und der `ADC_CTRL_TYPE_CURRENT_NOREV_BRAKE_ADC`-Verzweigung auditiert. Bei gleichzeitiger Gas- und Bremsanforderung wird der Bremszweig gewählt. Keine Änderung an der Bedienkennlinie.
6. Der echte portable `g30_sensorless_core.c` läuft in Host-C-Tests sowohl mit simulierten BEMF-Sektorfolgen als auch mit einer kontinuierlich rotierenden Flussvektor-Simulation vorwärts/rückwärts. Übernahme des Winkelbeobachters, positive/negative elektrische Geschwindigkeit und Fehlerfälle mit unplausiblen Spannungswerten geprüft. Die Phasenlage des tatsächlichen Motors ist dadurch **nicht** bestätigt.

**CI auf Commit `fa7201be588b599ad84684ed062aba78bad63be8`:**
- [21 Hosttests bestanden](https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/runs/39696472493).
- [UART-Recovery-Audit bestanden](https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/runs/39696472612).
- [G30P kompiliert und gelinkt](https://github.com/ZachWay9bot/SmartESC_STM32_v21b/actions/runs/39696472517): `text=50740`, `data=1364`, `bss=18728`. Flash-Load `52104 / 55296` Byte, **3192 Byte Flashreserve**. RAM-Sektion `20092 / 20480` Byte, **388 Byte nicht statisch belegte RAM-Reserve** (kein Maß für freien FreeRTOS-Heap oder Stack).
- Gesamtworkflow `failure` **ausschließlich an der unveränderten SHU-Freigabebedingung** `independent UART stock-restore unverified`. Der STM32-Kompilierungs- und Link-Schritt ist erfolgreich. Kein Flash-Paket veröffentlicht.

## Unveränderte, mögliche Restrisiken und Entscheidungen

### FOC-Beobachter, RUN-Zustandsmeldung

In `common_files/src/g30_sensorless.c`, `G30SL_CalcAvrgMecSpeedUnit()`:

- Nach `active_grace` gibt die Funktion `observer_seeded && observer_bad < 20` zurück.
- Im Kern existiert `g30sl_core_run_valid()`, die zusätzlich `observer_valid` fordert.
- **Damit ist theoretisch ein RUN-Zustand möglich, obwohl der Beobachter noch nicht die für `observer_valid` nötigen gültigen Samples gesammelt hat.**
- **Vorschlag, noch NICHT umgesetzt:** nach `active_grace` `g30sl_core_run_valid(&h->core)` verwenden. Vorteil: Motorlauf wird bei nicht bestätigtem Beobachter nicht als gültig beurteilt. Nachteile/Risiken: strengere Motorfehlerentscheidung könnte bei vorübergehend schwacher BEMF, falscher Stromkalibrierung oder zu kurzer Übergangszeit unerwartet Motorabschaltungen auslösen. **Alternative:** unverändert lassen und erst auf der Hardware `observer_good/bad/valid`, Rückmeldung und Fehlerfälle erfassen. Wegen der ausdrücklich vereinbarten Änderungsfreigabe wurde das Verhalten nicht ohne Zustimmung geändert.

### Weitere offene Nachweise

- Tatsächliche Strom-ADC-Skalierung, Offsets, Phasenreihenfolge und Stromvorzeichen auf dem vergossenen G30-identical-Controller.
- Verhältnis zwischen BEMF und elektrischer FOC-Rotorphase unter Last; simulierte Phasenlagen allein können Verdrahtungsfehler nicht erkennen.
- Motorparameter R/L/Flux aus VESC Tool Detect All, gespeicherte Parameter nach Neustart, unverändertes Rückflashen über **ausschließlich UART-IAP** (ST-LINK physisch nicht möglich).
- `lambda *= 2.0f` in der Detect-All-Flux-Routine ist noch durch echte Messdaten zu bestätigen und wurde deshalb **nicht geändert**.
- Stromverbrauch/-spitzen, Hardfault-/Stackreserven unter Last und echte Gas-/Brems- und Dashboard-Telegramme auf Hardware.
- Die verbleibende SHU-Freigabe erfordert den Nachweis eines unabhängigen UART-Stock-Restores. Bestehende Freigabe-/Recovery-Logik **nicht ändern** ohne gesonderte Erläuterung und ausdrückliche Freigabe.

## Hardware-Übergabe: nur noch diese Messungen

**Vor dem ersten Flash** UART-Stock-Restore/Wiederherstellung unabhängig nachweisen. Kein ST-LINK, kein Bootloader-/IAP-Experiment.

Danach mit frei drehendem Rad, `current-limited lab PSU` und physischem Abschalter:

1. **Coast-BEMF:** Alle drei ADC-Phasen bei ausgeschalteter PWM mit Drehrichtung und Drehzahl erfassen. Bei **15 Polpaaren**, Raddurchmesser 0,243 m und 3 km/h ergeben sich rechnerisch ca. 65,5 Rad-U/min, 982 elektrische U/min und 16,4 Hz elektrisch. Tatsächliche Phase-Reihenfolge, Vorzeichen und BEMF-Amplitude prüfen.
2. **Strommessung:** ADC1/ADC2-Stromoffsets bei stillstehendem Motor, `Ia/Ib/Ic` bei geringer zulässiger Last und Plausibilität der Summe `Ia+Ib+Ic≈0` erfassen. Überstrom **nicht absichtlich provozieren**.
3. **FOC Detect All:** R, L und Flux mit begrenzter Prüfstromversorgung messen. Danach Konfiguration über VESC Tool lesen, nach einem zulässigen Neustart erneut lesen. Überprüfung des bestehenden Faktors 2,0 gegen beobachtete BEMF-Flusskonstante.
4. **Anschieben und Übernahme:** Rad frei auf ca. 3 km/h beschleunigen, dann sehr wenig Gas. Übernahme des Beobachters und elektrische Drehzahl erfassen, Gas loslassen und Bremspriorität prüfen. Richtungswechsel und nachlassende BEMF beobachten, ohne Straßenbetrieb.
5. **Fehlerfälle:** Detect-Abbruch, Ausfall der Dashboard-Kommunikation und blockierter Motor nur innerhalb kontrollierter, zuvor freigegebener Prüfbedingungen. Keine unbeaufsichtigten Motorversuche.

### Änderungsgrenzen

Keine Änderungen an `g30_recovery_iap.c`, SHU-Freigabebedingung, Bootloader, IAP, Linker-Flashlayout oder an den 15 Polpaaren (VESC `si_motor_poles = 30`). Sonstige nicht angeforderte Motor- oder Sicherheitsverhaltensänderungen bleiben bis zur ausdrücklichen Freigabe Vorschläge.
