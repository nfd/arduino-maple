#define ON 1
#define OFF 0

void debug(int on);
void maple_tx_raw(unsigned char *buf, unsigned char length);
unsigned char *maple_rx_raw(unsigned char *buf, short skip_amt);
void maple_timer_test();
