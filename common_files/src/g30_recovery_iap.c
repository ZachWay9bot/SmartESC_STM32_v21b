#include "g30_recovery_iap.h"
#include "main.h"
#include <stdint.h>

#define REC_APP_BASE       0x08001000u
#define REC_STAGING_BASE   0x0800E800u
#define REC_STAGING_LIMIT  0x0801C000u
#define REC_STAGING_MAX    (REC_STAGING_LIMIT - REC_STAGING_BASE)
#define REC_CONTROL        0x0801F800u
#define REC_PAGE_SIZE      0x400u
#define REC_MAX_DATA       128u

enum {
    REC_OK=0, REC_ERR_SIZE=1, REC_ERR_ERASE=2, REC_ERR_WRITE=3,
    REC_ERR_UNLOCK=4, REC_ERR_INDEX=5, REC_ERR_BUSY=6,
    REC_ERR_FORM=7, REC_ERR_CRC=8, REC_ERR_OTHER=9
};

typedef struct {
    uint8_t key[16], iv[8];
    uint32_t offset;
} rec_tea_t;

typedef struct {
    uint32_t total, written, body_sum;
    uint8_t expected_index, begun, finalized, vector_ok;
    rec_tea_t tea;
} rec_iap_t;

typedef struct {
    uint8_t len, src, dst, cmd, index, data[REC_MAX_DATA];
} rec_frame_t;

typedef struct {
    uint8_t st, pos;
    uint16_t sum, rxcrc;
    rec_frame_t f;
} rec_parser_t;

static rec_iap_t s_iap;
static rec_parser_t s_parser;
/* Normal G30 application shares the early-recovery protocol decoder.
 * IAP writes are refused whenever the motor output is not off. */
static uint8_t s_app_mode;
static uint8_t s_app_flash_idle;


static uint32_t rd32(const uint8_t *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}
static void wr32(uint8_t *p, uint32_t v) {
    p[0]=(uint8_t)v; p[1]=(uint8_t)(v>>8); p[2]=(uint8_t)(v>>16); p[3]=(uint8_t)(v>>24);
}
static uint32_t rol16(uint32_t v) { return (v << 16) | (v >> 16); }

static void tea_init(rec_tea_t *s) {
    static const uint8_t k[16] = {
        0xFE,0x80,0x1C,0xB2,0xD1,0xEF,0x41,0xA6,
        0xA4,0x17,0x31,0xF5,0xA0,0x68,0x24,0xF0
    };
    for (unsigned i=0;i<16;i++) s->key[i]=k[i];
    for (unsigned i=0;i<8;i++) s->iv[i]=0;
    s->offset=0;
}
static void tea_decrypt(rec_tea_t *s, const uint8_t in[8], uint8_t out[8]) {
    uint32_t y=rd32(in), z=rd32(in+4);
    uint32_t k0=rd32(s->key), k1=rd32(s->key+4), k2=rd32(s->key+8), k3=rd32(s->key+12);
    uint32_t sum=0xC6EF3720u;
    for (unsigned i=0;i<32;i++) {
        z-=((y<<4)+k2)^(y+sum)^((y>>5)+k3);
        y-=((z<<4)+k0)^(z+sum)^((z>>5)+k1);
        sum-=0x9E3779B9u;
    }
    uint8_t t[8]; wr32(t,y); wr32(t+4,z);
    for (unsigned i=0;i<8;i++) { out[i]=t[i]^s->iv[i]; s->iv[i]=in[i]; }
    s->offset+=8u;
    if ((s->offset & 1023u)==0u) for (unsigned i=0;i<16;i++) s->key[i]=(uint8_t)(s->key[i]+i);
}

static int flash_wait(void) {
    uint32_t guard=8000000u;
    while ((FLASH->SR & FLASH_SR_BSY) && --guard) {}
    if (!guard) return -1;
    if (FLASH->SR & (FLASH_SR_PGERR | FLASH_SR_WRPRTERR)) return -2;
    return 0;
}
static void flash_clear(void) { FLASH->SR = FLASH_SR_EOP | FLASH_SR_PGERR | FLASH_SR_WRPRTERR; }
static int flash_unlock_rec(void) {
    if (!(FLASH->CR & FLASH_CR_LOCK)) return 0;
    FLASH->KEYR=FLASH_KEY1; FLASH->KEYR=FLASH_KEY2;
    return (FLASH->CR & FLASH_CR_LOCK) ? -1 : 0;
}
static void flash_lock_rec(void) { FLASH->CR |= FLASH_CR_LOCK; }
static int flash_erase_page_rec(uint32_t addr) {
    if (flash_wait()) return -1;
    flash_clear(); FLASH->CR |= FLASH_CR_PER; FLASH->AR=addr; FLASH->CR |= FLASH_CR_STRT;
    int r=flash_wait(); FLASH->CR &= ~FLASH_CR_PER;
    if (r) return r;
    for (uint32_t p=addr;p<addr+REC_PAGE_SIZE;p+=4u) if (*(volatile uint32_t*)p != 0xffffffffu) return -3;
    return 0;
}
static int flash_program_rec(uint32_t addr, const uint8_t *data, uint32_t len) {
    if ((addr & 1u) || (len & 1u)) return -1;
    for (uint32_t i=0;i<len;i+=2u) {
        if (flash_wait()) return -2;
        flash_clear(); FLASH->CR |= FLASH_CR_PG;
        uint16_t v=(uint16_t)data[i] | ((uint16_t)data[i+1] << 8);
        *(volatile uint16_t*)(addr+i)=v;
        int r=flash_wait(); FLASH->CR &= ~FLASH_CR_PG;
        if (r || *(volatile uint16_t*)(addr+i)!=v) return -3;
    }
    return 0;
}
static int control_write(uint32_t pending, uint32_t size) {
    uint8_t b[12]={0x5A,0x50,0x00,0x00,0,0,0,0,0,0,0,0};
    wr32(b+4,pending); wr32(b+8,size);
    if (flash_erase_page_rec(REC_CONTROL)) return -1;
    return flash_program_rec(REC_CONTROL,b,sizeof b);
}

static int vector_valid(const uint8_t *p) {
    uint32_t sp=rd32(p), pc=rd32(p+4);
    if ((sp & 0x2FFE0000u) != 0x20000000u || !(pc & 1u)) return 0;
    pc &= ~1u;
    return pc >= REC_APP_BASE && pc < REC_STAGING_BASE;
}
static void iap_init(void) {
    s_iap.total=s_iap.written=s_iap.body_sum=0;
    s_iap.expected_index=s_iap.begun=s_iap.finalized=s_iap.vector_ok=0;
    tea_init(&s_iap.tea);
}
static uint8_t iap_begin(const uint8_t *data, uint8_t len) {
    if (len != 4u) return REC_ERR_FORM;
    uint32_t n=rd32(data);
    if (n < 16u || n > REC_STAGING_MAX || (n & 7u)) return REC_ERR_SIZE;
    if (flash_unlock_rec()) return REC_ERR_UNLOCK;
    if (control_write(0u,0u)) { flash_lock_rec(); return REC_ERR_ERASE; }
    uint32_t erase_len=(n+REC_PAGE_SIZE-1u)&~(REC_PAGE_SIZE-1u);
    if (REC_STAGING_BASE+erase_len > REC_STAGING_LIMIT) { flash_lock_rec(); return REC_ERR_SIZE; }
    for (uint32_t p=REC_STAGING_BASE;p<REC_STAGING_BASE+erase_len;p+=REC_PAGE_SIZE) {
        if (flash_erase_page_rec(p)) { flash_lock_rec(); return REC_ERR_ERASE; }
    }
    flash_lock_rec();
    s_iap.total=n; s_iap.written=s_iap.body_sum=0; s_iap.expected_index=0;
    s_iap.begun=1; s_iap.finalized=s_iap.vector_ok=0; tea_init(&s_iap.tea);
    return REC_OK;
}
static uint8_t iap_write(uint8_t index, const uint8_t *data, uint8_t len) {
    if (!s_iap.begun || s_iap.finalized) return REC_ERR_BUSY;
    if (index != s_iap.expected_index) {
        if (index == (uint8_t)(s_iap.expected_index-1u)) return REC_OK;
        return REC_ERR_INDEX;
    }
    if (!len) return REC_ERR_FORM;
    uint32_t rem=s_iap.total-s_iap.written, use=len<rem?len:rem;
    if (!use || (use & 7u)) return REC_ERR_FORM;
    if (flash_unlock_rec()) return REC_ERR_UNLOCK;
    for (uint32_t off=0;off<use;off+=8u) {
        uint8_t dec[8]; tea_decrypt(&s_iap.tea,data+off,dec);
        if ((s_iap.written+off)==0u) {
            if (!vector_valid(dec)) { flash_lock_rec(); s_iap.begun=0; return REC_ERR_FORM; }
            s_iap.vector_ok=1;
        }
        uint32_t abs=s_iap.written+off, body_end=s_iap.total-4u;
        if (abs+4u<=body_end) s_iap.body_sum+=rd32(dec);
        if (abs+8u<=body_end) s_iap.body_sum+=rd32(dec+4);
        if (flash_program_rec(REC_STAGING_BASE+abs,dec,8u)) { flash_lock_rec(); return REC_ERR_WRITE; }
    }
    flash_lock_rec();
    s_iap.written+=use; s_iap.expected_index=(uint8_t)(s_iap.expected_index+1u);
    return REC_OK;
}
static uint8_t iap_finalize(const uint8_t *data, uint8_t len) {
    (void)data;
    if (len != 4u) return REC_ERR_FORM;
    if (!s_iap.begun || s_iap.finalized) return REC_ERR_BUSY;
    if (s_iap.written != s_iap.total || !s_iap.vector_ok) return REC_ERR_SIZE;
    uint32_t stored=*(volatile uint32_t*)(REC_STAGING_BASE+s_iap.total-4u);
    if (stored != ~rol16(s_iap.body_sum)) return REC_ERR_CRC;
    uint32_t sp=*(volatile uint32_t*)REC_STAGING_BASE;
    uint32_t pc=*(volatile uint32_t*)(REC_STAGING_BASE+4u);
    if ((sp&0x2FFE0000u)!=0x20000000u || !(pc&1u) || ((pc&~1u)<REC_APP_BASE) || ((pc&~1u)>=REC_STAGING_BASE)) return REC_ERR_FORM;
    if (flash_unlock_rec()) return REC_ERR_UNLOCK;
    if (control_write(1u,s_iap.total)) { flash_lock_rec(); return REC_ERR_WRITE; }
    flash_lock_rec(); s_iap.finalized=1; s_iap.begun=0;
    return REC_OK;
}

static void gpio_nibble(GPIO_TypeDef *g, unsigned pin, uint32_t nib) {
    volatile uint32_t *r=(pin<8u)?&g->CRL:&g->CRH;
    unsigned sh=(pin&7u)*4u; *r=(*r&~(0xFu<<sh))|((nib&0xFu)<<sh);
}
static void uart_init_rec(void) {
    RCC->APB2ENR |= RCC_APB2ENR_AFIOEN | RCC_APB2ENR_IOPBEN | RCC_APB2ENR_USART1EN;
    AFIO->MAPR |= AFIO_MAPR_USART1_REMAP;
    gpio_nibble(GPIOB,6u,0xBu); gpio_nibble(GPIOB,7u,0x4u);
    USART1->CR1=0; USART1->BRR=556u; USART1->CR1=USART_CR1_UE|USART_CR1_TE|USART_CR1_RE;
}
static int uart_getc_rec(void) {
    if (!(USART1->SR & (USART_SR_RXNE|USART_SR_ORE))) return -1;
    return (int)(uint8_t)USART1->DR;
}
static void uart_putc_rec(uint8_t c) { while (!(USART1->SR&USART_SR_TXE)){} USART1->DR=c; }
static void uart_wait_rec(void) { while (!(USART1->SR&USART_SR_TC)){} }

static int parser_push(uint8_t b, rec_frame_t *out) {
    rec_parser_t *p=&s_parser;
    switch (p->st) {
    case 0: if (b==0x5A) p->st=1; break;
    case 1: if (b==0xA5) p->st=2; else p->st=(b==0x5A)?1:0; break;
    case 2: if (b>REC_MAX_DATA) {p->st=0;break;} p->f.len=b;p->sum=b;p->st=3;break;
    case 3: p->f.src=b;p->sum+=b;p->st=4;break;
    case 4: p->f.dst=b;p->sum+=b;p->st=5;break;
    case 5: p->f.cmd=b;p->sum+=b;p->st=6;break;
    case 6: p->f.index=b;p->sum+=b;p->pos=0;p->st=p->f.len?7:8;break;
    case 7: p->f.data[p->pos++]=b;p->sum+=b;if(p->pos>=p->f.len)p->st=8;break;
    case 8: p->rxcrc=b;p->st=9;break;
    case 9:
        p->rxcrc|=(uint16_t)b<<8;
        p->st=0;
        if (p->rxcrc==(uint16_t)~p->sum) { *out=p->f; return 1; }
        break;
    default: p->st=0; break;
    }
    return 0;
}
static void send_frame(uint8_t dst,uint8_t cmd,uint8_t index,const uint8_t *data,uint8_t len) {
    uint16_t sum=(uint16_t)len+0x20u+dst+cmd+index;
    uart_putc_rec(0x5A);uart_putc_rec(0xA5);uart_putc_rec(len);uart_putc_rec(0x20);
    uart_putc_rec(dst);uart_putc_rec(cmd);uart_putc_rec(index);
    for(uint8_t i=0;i<len;i++){uint8_t v=data?data[i]:0;sum+=v;uart_putc_rec(v);}
    uint16_t crc=(uint16_t)~sum;uart_putc_rec((uint8_t)crc);uart_putc_rec((uint8_t)(crc>>8));
}
static void ack(uint8_t dst,uint8_t result){send_frame(dst,0x0Bu,result,0,0);}

static uint16_t map_word(uint8_t idx) {
    static const uint8_t sn[14]={'X','B','O','T','R','C','V','1','V','0','0','0','0','1'};
    if (idx>=16u&&idx<23u){unsigned o=(idx-16u)*2u;return(uint16_t)sn[o]|((uint16_t)sn[o+1]<<8);}
    if (idx==26u) return 0x0001u;
    if (idx>=218u&&idx<224u){const uint8_t*uid=(const uint8_t*)0x1FFFF7E8u;unsigned o=(idx-218u)*2u;return(uint16_t)uid[o]|((uint16_t)uid[o+1]<<8);}
    return 0u;
}
static void dispatch(const rec_frame_t *f) {
    if (f->dst!=0x20u) return;
    if (f->cmd==0x01u && f->len==1u) {
        uint8_t n=f->data[0]; if(n>REC_MAX_DATA)n=REC_MAX_DATA; uint8_t out[REC_MAX_DATA];
        for(uint8_t i=0;i<n;i++){uint16_t w=map_word((uint8_t)(f->index+(i>>1)));out[i]=(uint8_t)(w>>((i&1u)*8u));}
        send_frame(f->src,0x04u,f->index,out,n); return;
    }
    if (s_app_mode && f->cmd>=0x07u && f->cmd<=0x0Au &&
        !s_app_flash_idle) { ack(f->src,REC_ERR_BUSY); return; }
    if (f->cmd==0x07u){ack(f->src,iap_begin(f->data,f->len));return;}
    if (f->cmd==0x08u){ack(f->src,iap_write(f->index,f->data,f->len));return;}
    if (f->cmd==0x09u){ack(f->src,iap_finalize(f->data,f->len));return;}
    if (f->cmd==0x0Au){
        if (!s_iap.finalized){ack(f->src,REC_ERR_BUSY);return;}
        ack(f->src,REC_OK);uart_wait_rec();HAL_Delay(10);NVIC_SystemReset();for(;;){}
    }
    if (f->cmd==0xF0u) {
        static const uint8_t d[8]={'R','C','V','1',0,0,0,1};
        send_frame(f->src,0xF0u,0,d,sizeof d);
    }
}

void G30Recovery_AppInit(void) {
    s_parser.st = s_parser.pos = 0u;
    s_parser.sum = s_parser.rxcrc = 0u;
    iap_init();
    s_app_mode = 1u;
}

bool G30Recovery_AppIapActive(void) {
    return s_app_mode && (s_iap.begun || s_iap.finalized);
}

void G30Recovery_AppPushByte(uint8_t byte, bool flash_idle) {
    rec_frame_t f;
    if (!parser_push(byte,&f)) return;
    s_app_flash_idle = flash_idle ? 1u : 0u;
    dispatch(&f);
}

void G30Recovery_CheckAndRun(void) {
    if (HAL_GPIO_ReadPin(PWR_BTN_GPIO_Port,PWR_BTN_Pin)!=GPIO_PIN_SET) return;
    uint32_t t0=HAL_GetTick();
    while ((uint32_t)(HAL_GetTick()-t0)<3000u) {
        if (HAL_GPIO_ReadPin(PWR_BTN_GPIO_Port,PWR_BTN_Pin)!=GPIO_PIN_SET) return;
    }

    /* Hard recovery mode: power held, bridge never initialized or armed. */
    HAL_GPIO_WritePin(TPS_ENA_GPIO_Port,TPS_ENA_Pin,GPIO_PIN_SET);
    HAL_GPIO_WritePin(REAR_LED_GPIO_Port,REAR_LED_Pin,GPIO_PIN_SET);
    uart_init_rec(); iap_init(); s_parser.st=s_parser.pos=0;s_parser.sum=s_parser.rxcrc=0;

    for (;;) {
        int ch=uart_getc_rec();
        if (ch>=0) { rec_frame_t f; if (parser_push((uint8_t)ch,&f)) dispatch(&f); }
    }
}
