/*
 * m365
 *
 * Copyright (c) 2021 Jens Kerrinnes
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of
 * this software and associated documentation files (the "Software"), to deal in
 * the Software without restriction, including without limitation the rights to
 * use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
 * the Software, and to permit persons to whom the Software is furnished to do so,
 * subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
 * FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
 * COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
 * IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
*/

#ifndef TASK_LED_H_
#define TASK_LED_H_

#include "cmsis_os.h"
#include <stdbool.h>

extern osThreadId_t task_LED_handle;

typedef enum {
	BRAKE_LIGHT_ON,
	BRAKE_LIGHT_OFF
}en_brake;

void task_LED_init();
void task_LED_set_brake_light(en_brake mode);

/* G30 STAR/DELTA helper state. On non-G30 targets these return false. */
bool task_delta_coast_required(void);
bool task_delta_is_active(void);
bool task_delta_setup_force(bool delta);
void task_delta_setup_release(void);
bool task_delta_setup_active(void);




#endif /* TASK_LED_H_ */

