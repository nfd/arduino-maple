#include <inttypes.h>
#include <avr/io.h>
#include <util/delay.h>
#include <stdio.h>
#include <stdbool.h>
#include "libmaple.h"

// Serial port setup
#define BAUD 57600
#define USE_2X 1
#include <util/setbaud.h>

FILE uart;

static void uart_putchar(uint8_t c) {
    if (c == '\n') {
		loop_until_bit_is_set(UCSR0A, UDRE0); /* Wait until data register empty. */
		UDR0 = '\r';
    }
    loop_until_bit_is_set(UCSR0A, UDRE0); /* Wait until data register empty. */
    UDR0 = c;
}

static int stdio_uart_putchar(char c, FILE *handle)
{
	(void) handle;

	uart_putchar(c);
	return 0;
}

static uint8_t uart_getchar(void) {
    loop_until_bit_is_set(UCSR0A, RXC0); /* Wait until data exists. */
    return UDR0;
}

static int stdio_uart_getchar(FILE *handle)
{
	(void) handle;
	return (int)uart_getchar();
}

static void uart_init(void) {
    UBRR0H = UBRRH_VALUE;
    UBRR0L = UBRRL_VALUE;

#if USE_2X
    UCSR0A |= _BV(U2X0);
#else
    UCSR0A &= ~(_BV(U2X0));
#endif

    UCSR0C = _BV(UCSZ01) | _BV(UCSZ00); /* 8-bit data */ 
    UCSR0B = _BV(RXEN0) | _BV(TXEN0);   /* Enable RX and TX */

	fdev_setup_stream(&uart, stdio_uart_putchar, stdio_uart_getchar, _FDEV_SETUP_RW);
	stdout = &uart;
	stdin = &uart;
}

struct maplepacket {
	unsigned char data_len; /* Bytes: header, data, and checksum */
	unsigned short data_len_rx; /* For Rx -- didn't realise we could get up to 512 bytes */

	unsigned char data[1536]; /* Our maximum packet size */
} packet;

void setup()
{
	// Initialise serial port
	uart_init();

	// Maple bus data pins as output -- NB needs corresponding changes in libMaple.S
	DDRB = 0xff;

	// Secondary pins are always tristate (floating and input).
	DDRC = 0x0;
	PORTC = 0x0;

	//puts("Hi there \n");
}

unsigned char compute_checksum(unsigned char data_bytes)
{
	unsigned char *ptr = packet.data;
	int count;
	unsigned char checksum = 0;

	for(count = 0; count < data_bytes + 4; count ++) {
		checksum ^= *ptr;
		ptr++;
	}
	return checksum;
}

/* Turn logic-analyser-style reads into a bit sequence. */
void debittify()
{
	// TODO -- done in Python currently.
}

bool
maple_transact(short skip_amt)
{
	unsigned char *rx_buf_end;
	//unsigned char *rx_buf_ptr;

	// debug
	/*
	packet.header[0] = 0; // Number of additional words in frame
	packet.header[1] = 0; // Sender address = Dreamcast
	packet.header[2] = 1; //(1 << 5); // Recipient address = main peripheral on port 0
	packet.header[3] = 1; // Command = request device information
	packet.data[0]   = compute_checksum(0);
	packet.data_len  = 5;
	*/

	/*packet.header[0] = (192 + 4) / 4; // Number of additional words in frame
	packet.header[1] = 0; // Sender address = Dreamcast
	packet.header[2] = 1;
	packet.header[3] = 12; // block write
	packet.data[0]   = 0x4; // LCD
	packet.data[1]   = 0; // partition
	packet.data[2]   = 0; // phase
	packet.data[3]   = 0; // block number
	packet.data[4]   = 0xff;
	packet.data[5]   = 0x0f;
	packet.data[6]   = 0xff;
	packet.data[192 + 4] = compute_checksum(192 + 4);
	packet.data_len  = 4 + 192 + 4 + 1;
	*/

	maple_tx_raw(packet.data, packet.data_len);
	rx_buf_end = maple_rx_raw(packet.data, skip_amt);

	packet.data_len_rx = (rx_buf_end - packet.data);

	// TODO debittify here rather than in Python: it's simpler in C and
	// significantly reduces transfer time.

	return true;

	// debug
	/*Serial.print("All done \n");
	Serial.println((int)(rx_buf_end - (&(packet.header[0]))), HEX);
	rx_buf_ptr = (&(packet.header[0]));
	while(rx_buf_ptr <= rx_buf_end) {
		Serial.println(*rx_buf_ptr, HEX);
		rx_buf_ptr ++;
	}
	*/
}

/* Read packet to send from the controller. */
bool
read_packet(void)
{
	/* First byte: #bytes in packet (including header and checksum)*/
	packet.data_len = uart_getchar();
	if(packet.data_len > 0) {
		unsigned char *data = packet.data;
		int i;
		for(i = 0; i < packet.data_len; i++) {
			*data = uart_getchar();
			data ++;
		}
		return true;
	} else {
		return false;
	}
}

bool
packet_dest_is_maple(void)
{
	return packet.data_len > 0;
}

void
send_packet(void)
{
	uart_putchar((packet.data_len_rx & 0xff00) >> 8);
	uart_putchar(packet.data_len_rx & 0xff);
	if(packet.data_len_rx) {
		int i;
		uint8_t *data = packet.data;
		for (i = 0; i < packet.data_len_rx; i++) {
			uart_putchar(data[i]);
		}
	}
}

void main() __attribute__ ((noreturn));
void main(void) {
    setup();

	// maple_transact(); for (;;) ;
	debug(1);

#if 0
	while(1) {
		puts("before timer test\n");
		_delay_ms(500);
		maple_timer_test();
		puts("after timer test\n");
		_delay_ms(500);
	}
#endif

    for (;;) {
		//debug(0);
		read_packet();
		debug(0);

		if(packet_dest_is_maple()) {
			maple_transact(0);
			//debug(1);
			send_packet();
		} else {
			// Debug
			uart_putchar(1);
		}
		debug(1);
	}
}

