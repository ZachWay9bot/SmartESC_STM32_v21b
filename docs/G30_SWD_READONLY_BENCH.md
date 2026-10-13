# G30D Gen1: read-only ST-Link register capture (Windows)
**STATUS: READ ONLY; no motor enable; no flash/write/reset intended.**

Stock DRV126 is the reference. Keep wheel free, avoid throttle and motor-start commands. Connect all SWD wires with power off, inspect for shorts, then power the scooter normally. SWD HOTPLUG can affect timing; captures across multiple commands are not atomic.

## Quick stock scan (PowerShell with STM32CubeProgrammer CLI)
```powershell
$cli = "C:\Program Files\STMicroelectronics\STM32Cube\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe"
mkdir G30_stock_SWD -Force
& $cli -c port=SWD mode=HOTPLUG freq=100 --upload 0x08001000 0x8 G30_stock_SWD\VECTORS.bin
& $cli -c port=SWD mode=HOTPLUG freq=100 --upload 0x40012C00 0x48 G30_stock_SWD\TIM1.bin
& $cli -c port=SWD mode=HOTPLUG freq=100 --upload 0x40021000 0x24 G30_stock_SWD\RCC.bin
& $cli -c port=SWD mode=HOTPLUG freq=100 --upload 0x40012400 0x3C G30_stock_SWD\ADC1.bin
& $cli -c port=SWD mode=HOTPLUG freq=100 --upload 0x40012800 0x3C G30_stock_SWD\ADC2.bin
& $cli -c port=SWD mode=HOTPLUG freq=100 --upload 0x40010800 0x10 G30_stock_SWD\GPIOA.bin
& $cli -c port=SWD mode=HOTPLUG freq=100 --upload 0x40010C00 0x10 G30_stock_SWD\GPIOB.bin
& $cli -c port=SWD mode=HOTPLUG freq=100 --upload 0x40011000 0x10 G30_stock_SWD\GPIOC.bin
& $cli -c port=SWD mode=HOTPLUG freq=100 --upload 0x40010004 0x4 G30_stock_SWD\AFIO_MAPR.bin
& $cli -c port=SWD mode=HOTPLUG freq=100 --upload 0x40004408 0x10 G30_stock_SWD\USART2_CFG.bin
Compress-Archive -Path G30_stock_SWD\* -DestinationPath G30_stock_SWD.zip -Force
```

`--upload` reads memory into a local file. No `--download`, `--write`, `--erase`, or `--reset` is used.

Important: USART2 starts at **0x40004408**, skipping SR/DR; do not read USART2 DR (0x40004404) on a running link, as it may consume data. ADC regions stop before injected data registers (JDR1 at +0x3C). Some diagnostic reads may still disturb MCU timing. Decode 32-bit little-endian values at documented offsets.

## Addresses for manual comparison

| Register | Address / block offset |
| --- | --- |
| TIM1 CR1 | 0x40012C00 +0x00 |
| TIM1 CCER | +0x20 |
| TIM1 PSC | +0x28 |
| TIM1 ARR | +0x2C |
| TIM1 RCR | +0x30 |
| TIM1 CCR4 | +0x40 |
| TIM1 BDTR | +0x44 |
| ADC1/2 CR2 | 0x40012400/0x40012800 +0x08 |
| ADC1/2 JSQR | +0x38 |
| GPIOA/B/C CRH | 0x40010800/0x40010C00/0x40011000 +0x04 |
| GPIOA/B/C ODR | +0x0C |
| RCC CFGR | 0x40021004 |

Use stock first; a second capture on the experimental firmware is relevant **only after physical gate-driver polarity and pin behavior are electrically characterized**. A source-level GPIO LOW is not proof of gate-driver disable. Even if output lines read LOW and BDTR.MOE=0, motor enable remains UNVALIDATED.
