# Firmware builds

## Aktuelle Entwicklung: BENCH UART-IAP ohne SHU

Bis zur ausdruecklichen Wiederfreigabe durch den Projektinhaber wird im
Entwicklungs-Build **keine ScooterHacking-ZIP (SHU)** erzeugt oder publiziert.
Der Controller wird am Pruefstand ohne Dashboard entwickelt.

- Aktiver Branch: `audit/vesc-g30-20261021`, Draft PR #23.
- GitHub Action: **Build G30 Bench UART-IAP on commit**.
- Build-Artefakte: rohe `g30p.bin`, ELF/MAP, verschluesseltes
  `SmartESC_G30_BENCH_IAP_Driver.bin`, JSON-Manifest mit Hashes und RAM-Audit.
- Das IAP-Driver.bin ist ein **ungetesteter Bench-Kandidat**, kein
  hardwareverifizierter Stand und keine motorseitige Fahrfreigabe.
- Der SHU-Build-Workflow ist entfernt und der Tag-Release erstellt keine
  SHU-ZIP. Das Skript `tools/make_shu_zip.py` bleibt unveraendert fuer
  eine spaetere explizite Freigabe erhalten.
- Flash-/Recovery-Code, UART-Protokoll, Flashadressen und Bootloader bleiben
  unveraendert.

## Historisch veroeffentlichte Dateien unter firmware/v0.8.7

**Die bestehenden v0.8.7-Downloads sind Altartefakte und NICHT identisch mit
dem laufenden Bench-Entwicklungsstand.** Nicht als aktuelle Bench-Firmware
interpretieren oder ohne passende Hardwarepruefung flashen.

Reference CI build #87:

- FIRM.bin: 55240 bytes
- FIRM.bin.enc: 55248 bytes
- SHU ZIP SHA-256: `84e8e3187992a88046a75d519e64ed7cb27962605bffbe5a877a33652a6457c9`
- IAP Driver.bin SHA-256: `0fb3bc6d6800ed676c3a39845c8787a896b706e2b9fe1ef56815a651c24e584e`

Fuer aktuelle Entwicklungsbinaries den **Build G30 Bench UART-IAP on commit** verwenden. Die folgenden Hashes beziehen sich nur auf die historischen v0.8.7-Artefakte.


## Published repository files

The versioned v0.8.7 binaries are committed directly under `firmware/v0.8.7/`.

Current repository-published hashes:

```text
84e8e3187992a88046a75d519e64ed7cb27962605bffbe5a877a33652a6457c9  SmartESC_G30_NativeDash_v0.8.7_SHU.zip
0fb3bc6d6800ed676c3a39845c8787a896b706e2b9fe1ef56815a651c24e584e  SmartESC_G30_NativeDash_v0.8.7_IAP_Driver.bin
```

The encrypted IAP payload is byte-identical to the validated build #87 payload. The ZIP hash changed when the SHU archive was reproducibly regenerated and committed because ZIP container metadata differs; firmware payload hashes remain the meaningful binary identity.
