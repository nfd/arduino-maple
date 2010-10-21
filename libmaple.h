#define ON 1
#define OFF 0

extern "C" {
void debug(int on);
void maple_tx_raw(unsigned char *buf, unsigned char length);
unsigned char *maple_rx_raw(unsigned char *buf);
void maple_timer_test();
}
