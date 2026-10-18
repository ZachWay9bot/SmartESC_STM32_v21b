/****************************************************************************/
//  Function: C file ninebot communication
//  Author:   Camilo Ruiz
//  Date:    october 10 2017
//
//  This library is free software; you can redistribute it and/or
//  modify it under the terms of the GNU Lesser General Public
//  License as published by the Free Software Foundation; either
//  version 2.1 of the License, or (at your option) any later version.
//
//  This library is distributed in the hope that it will be useful,
//  but WITHOUT ANY WARRANTY; without even the implied warranty of
//  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
//  Lesser General Public License for more details.
//
// I am not responsible of any damage caused by the misuse of this library
// use at your own risk
//
// If you modify this or use this, please don't delete my name and give me the credits
// Greetings from Colombia :) 
// Hardware port by ub4raf
/****************************************************************************/
#include "ninebot.h"
#include "m365_register_map.h"

enum{
	NIN_IDLE, NIN_HEAD, NIN_LEN, NIN_SRC, NIN_DST, NIN_CMD, NIN_ARG,
	NIN_DATA, NIN_CRC0, NIN_CRC1
};

uint16_t ninebot_parse(uint8_t data, NinebotPack *message){
	static uint8_t state = NIN_IDLE;
	static uint8_t cnt = 0;
	static uint16_t checksum = 0;

	switch(state){
	case NIN_IDLE:
		if(data == NinebotHeader0) state = NIN_HEAD;
		break;
	case NIN_HEAD:
		state = (data == NinebotHeader1) ? NIN_LEN :
		        ((data == NinebotHeader0) ? NIN_HEAD : NIN_IDLE);
		break;
	case NIN_LEN:
		if(data > NinebotMaxPayload){ state = NIN_IDLE; break; }
		message->len = data; checksum = data; cnt = 0; state = NIN_SRC;
		break;
	case NIN_SRC:
		message->src = data; checksum += data; state = NIN_DST; break;
	case NIN_DST:
		message->dst = data; checksum += data; state = NIN_CMD; break;
	case NIN_CMD:
		message->cmd = data; checksum += data; state = NIN_ARG; break;
	case NIN_ARG:
		message->arg = data; checksum += data;
		state = message->len ? NIN_DATA : NIN_CRC0;
		break;
	case NIN_DATA:
		message->payload[cnt++] = data; checksum += data;
		if(cnt >= message->len) state = NIN_CRC0;
		break;
	case NIN_CRC0:
		message->CheckSum[0] = data; state = NIN_CRC1; break;
	case NIN_CRC1: {
		message->CheckSum[1] = data;
		uint16_t got = (uint16_t)message->CheckSum[0] | ((uint16_t)data << 8);
		uint16_t want = (uint16_t)~checksum;
		state = NIN_IDLE;
		return got == want ? 0 : 1;
	}
	default:
		state = NIN_IDLE; break;
	}
	return 1;
}

void addCRC(uint8_t * message, uint8_t size){
    unsigned long cksm = 0;
    for(int i = 2; i < size - 2; i++) cksm += message[i];
    cksm ^= 0xFFFF;
    message[size - 2] = (uint8_t)(cksm&0xFF);
    message[size - 1] = (uint8_t)((cksm&0xFF00) >> 8);
}
