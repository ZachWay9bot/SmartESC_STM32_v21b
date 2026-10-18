@echo off
setlocal
if "%~1"=="" (
  echo Nutzung: RECOVERY_FLASH_COM9.cmd firmware_SHU.zip
  echo oder:    RECOVERY_FLASH_COM9.cmd SmartESC_G30_NativeDash_v0.8.7_IAP_Driver.bin
  echo.
  echo 1. Controller AUS
  echo 2. USB-UART an PB6/PB7/GND anschliessen
  echo 3. Powerbutton beim Einschalten mindestens 3 Sekunden halten
  echo 4. Gewuenschte Firmware auf diese CMD ziehen
  pause
  exit /b 2
)
py "%~dp0recovery_iap_flash.py" COM9 "%~1"
pause
