# SmartESC G30 startup defect — 25 October 2026

The exact BENCH-278 ELF has SVC, PendSV and SysTick vectors all at weak Default_Handler 0x0800D035 and contains no LED task entry. Its main calls neither task_init() nor vTaskStartScheduler(); vTaskSwitchContext() alone does not start FreeRTOS. This is a real linked-image defect. It is consistent with no VESC response and a steady LED, but does not prove physical damage or recovery reachability on the flashed replacement.

This change restores task_init() before application configuration, starts the scheduler normally, and adds a read-only linked ELF check before packaging. No bootloader, IoT recovery, IAP layout, motor parameters or motor-control algorithm change. BENCH-278 fails the new check, as expected. New image is NOT hardware verified and must NOT be installed on another sealed controller based only on a green build.

Current physical handoff: user stopped work on the previously flashed replacement, and intends to use a known-good controller with ST-Link access. Before any new hardware write, preserve its original flash/option bytes and establish the actual ST-Link restore procedure. Stock DRV1.8.7 is not needed as a SmartESC prerequisite. There are no pending RemoteLab hardware commands.
