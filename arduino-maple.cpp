#include "libmaple.h"

#include "WProgram.h"
void setup(void);
void loop(void);

struct maplepacket {
	unsigned char data_len; /* Including header and trailing checksum */

	unsigned char header[4];
	unsigned char data[256]; /* Our maximum packet size */
} packet;

void setup()
{
	Serial.begin(57600);

	pinMode(7, OUTPUT); // debug pin
	pinMode(13, OUTPUT); // More different debug pin

	// Maple bus data pins
	pinMode(8, INPUT);
	digitalWrite(8, HIGH);
	pinMode(9, INPUT);
	digitalWrite(9, HIGH);
}

bool maple_transact();

unsigned char compute_checksum(unsigned char data_bytes)
{
	unsigned char *ptr = &(packet.header[0]);
	int count;
	unsigned char checksum = 0;

	for(count = 0; count < data_bytes + 4; count ++) {
		checksum ^= *ptr;
		ptr++;
	}
	return checksum;
}

bool
maple_transact()
{
	unsigned char *rx_buf_end;
	unsigned char *rx_buf_ptr;

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

	maple_tx_raw(&(packet.header[0]), packet.data_len);
	rx_buf_end = maple_rx_raw(&(packet.header[0]));
	packet.data_len  = (unsigned char)(rx_buf_end - (&(packet.header[0])));

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
	while(!(Serial.available()))
		;
	packet.data_len = Serial.read();
	if(packet.data_len > 0) {
		unsigned char *data = &(packet.header[0]);
		for(int i = 0; i < packet.data_len; i++) {
			while(!(Serial.available()))
				;
			*data = Serial.read();
			data ++;
		}
		return true;
	} else {
		return false;
	}
}

void
send_packet(void)
{
	Serial.write(packet.data_len);
	Serial.write(&(packet.header[0]), packet.data_len);
}

void main() __attribute__ ((noreturn));
void main(void) {
    init();
    setup();

	// maple_transact(); for (;;) ;

    for (;;) {
		debug(0);
		if(read_packet()) {
			maple_transact();
			debug(1);
			send_packet();
		}
	}
}

