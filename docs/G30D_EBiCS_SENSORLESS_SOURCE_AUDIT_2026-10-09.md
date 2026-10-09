# G30D Gen1 Sensorless-Port: unabhängiger Source-Audit (09.10.2026)

**SOURCE ONLY, NO FLASH / NO MOTOR RELEASE.** Dieser Branch verändert **keine** bestehende G30-/M365-Produktionsfirmware.

## Ergebnis

Die Firmware `Koxx3/SmartESC_STM32_v2` besitzt im Branch `vesc_comp` ein `g30p`-CubeIDE-Projekt mit G30-spezifischem Pinmapping. Der MCSDK-Regelpfad ist bisher Hall-basiert: `common_files/src/mc_tasks.c` nutzt `HALL_Init`, `HALL_CalcElAngle` sowie `HALL_M1` als Positionsquelle. Dies ist **kein funktionierender sensorloser G30-Port**.

Aus dem Upstream `g30p/Inc/main.h`:
- PWM: PA8/PA9/PA10 und PB13/PB14/PB15 (TIM1 CH1/2/3 mit komplementären Ausgängen).
- Phase current ADC: PA3/PA4/PA5; VBUS: PA1.
- Power button: PC14; im Upstream `TPS_ENA` auf PA11.
- Ninebot dashboard: PA2; Halls: PB4/PB5/PB0.
- Diese Angaben sind **Code-Referenzen**, keine verifizierte Schaltplan-/Board-Qualifikation.

## Wichtigster neuer Blocker: Stock-IAP

Im unveränderten Upstream-G30P-Linker `g30p/STM32CubeIDE/STM32F103C8TX_FLASH.ld` steht:

```text
FLASH (rx) : ORIGIN = 0x8000000, LENGTH = 128K
```

G30P `common_files/inc/product.h` enthält:

```c
#define APP_PAGE 126
#define CONF_PAGE 127
```

Das passt **nicht** zur 128-KiB-Flashmap des untersuchten Ninebot-DRV126-Stock-Dumps:
- Stock-Bootloader 0x08000000..0x08000FFF.
- Stock-App 0x08001000..0x0800E7FF (max. 55.296 Byte Slot; derzeit konservativ 50 KiB als IAP-Ziel).
- Update-Staging ab 0x0800E800.
- Original-Updatekontrollseiten 0x0801F800 (Seite 126), 0x0801FC00 (Seite 127).

**Die SmartESC-Config würde diese beiden Kontrollseiten verwenden!** Eine fertige SmartESC-G30P-BIN ist daher **nicht** einfach über Stock-BLE/SHU installierbar und würde mit ihrem Origin beim vollständigen ST-Link-Flash den Stock-Bootloader ersetzen.

Die veröffentlichte v0.3.5 `m365.bin` ist 82.024 Byte groß (M365, keine G30-BIN). Das illustriert die Größenfrage; ein G30-Binärmaß ist damit **nicht** belegt.

## Sensorless-Quelle

`EBiCS/EBiCS_Firmware` Branch `Sensorless_VESC` enthält `Src/FOC.c`, dort `observer_update()`, einen nichtlinearen Flux-Beobachter mit Winkelgewinnung. Die originale EBiCS-Anwendung nutzt eigenes `CAL_I`, `CAL_V`, `RESISTANCE`, `INDUCTANCE`, `FLUX_LINKAGE`, `GAMMA` und Open-Loop-Start. **Diese Werte sind nicht für G30 validiert**. Es ist kein Drop-in zu SmartESC-MCSDK.

`EBiCS/EBiCS_motor_FOC` zeigt zusätzlich einen eigenständigen F103-FOC-Kern mit M365-Demo, allerdings ohne automatische G30-Kompatibilität.

## Nächster Implementierungsmeilenstein

1. Eigenständiger source-only MCU-Build mit Stock-App-Origin 0x08001000, VTOR, ohne Schreibzugriff auf Update-/Config-Seiten.
2. Sichere Power-Hold-/Button-/Dashboard-Verifikation ohne aktive PWM.
3. TIM1-CH4-getriggerte ADC-Diagnose, Hardware-Phasenstrom-Offset/Verstärker und VBUS gegen Multimeter abgleichen.
4. EBiCS-Observer isoliert mit aufgezeichneten Strom-/Spannungswerten testen; Observer-CPU-Budget und Lock-Kriterium messen.
5. Erst nach echter Hardwarekalibrierung separater GATE-ENABLED Bench-Branch. Kein 14s-Test, kein blindes Flash.

**Dieser Branch enthält keine behauptete funktionierende Motorfirmware.**

Quellen:
- https://github.com/Koxx3/SmartESC_STM32_v2/tree/vesc_comp/g30p
- https://github.com/Koxx3/SmartESC_STM32_v2/blob/vesc_comp/common_files/inc/product.h
- https://github.com/EBiCS/EBiCS_Firmware/tree/Sensorless_VESC
- https://github.com/EBiCS/EBiCS_motor_FOC
