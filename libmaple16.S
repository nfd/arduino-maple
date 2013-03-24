; Functions for Maple bus support on devices with 16-bit program counters (328)

#include <avr/io.h>

; reg usage faq: http://www.nongnu.org/avr-libc/user-manual/FAQ.html#faq_reg_usage
; essentially we can play with regs 18 to 27 and 30 and 31.

.global debug
.global maple_tx_raw
.global maple_rx_raw
.global maple_timer_test
.global TIMER2_OVF_vect

#define intsave r31
#define intwork r20
#define tmp1 r18
#define tmp2 r19
#define rport2 r21
#define rport r30

; Maple1 is on bit 0 of PORTMAPLE -- mask of 1:
#define bitmaple1 0
#define maskmaple1 1
; maple5 is on bit 1 -- mask of 10:
#define bitmaple5 1
#define maskmaple5 2

#define PORTMAPLE PORTB
#define PINMAPLE PINB
#define DDRMAPLE DDRB

.macro maple_high pin
	SBI _SFR_IO_ADDR(PORTMAPLE), \pin
.endm

.macro maple_low pin
	CBI _SFR_IO_ADDR(PORTMAPLE), \pin
.endm

.macro debug_pin_high
	SBI _SFR_IO_ADDR(PORTD), 7
.endm

.macro debug_pin_low
	CBI _SFR_IO_ADDR(PORTD), 7
.endm

.macro debug_pin_flip
	IN tmp1, _SFR_IO_ADDR(PORTD)
	ANDI tmp1, 0x80
	BREQ 1f
	debug_pin_low
	RJMP 2f
1:	debug_pin_high
2:	
.endm

.macro delayquarter
	nop
	nop
	nop
	nop
.endm

; Delay half a uS. CALL takes 4 cycles, RET takes 4 cycles,
; 8 cycles is half a microsecond at 16MHz, voila.
delayhalf:
	ret

maple_tx_start:
	maple_high bitmaple1
	maple_high bitmaple5
	delayquarter
	; Start of sequence: pin 1 goes low, pin 5 goes high.
	maple_low bitmaple1
	maple_high bitmaple5
	delayquarter
	; Toggle pin 5 four times: 1
	maple_low bitmaple5
	delayquarter
	maple_high bitmaple5
	delayquarter
	; 2
	maple_low bitmaple5
	delayquarter
	maple_high bitmaple5
	delayquarter
	; 3
	maple_low bitmaple5
	delayquarter
	maple_high bitmaple5
	delayquarter
	; 4
	maple_low bitmaple5
	delayquarter
	maple_high bitmaple5
	delayquarter
	; End of sequence: pin 1 goes high, pin 5 goes low.
	maple_high bitmaple1
	delayquarter
	maple_low bitmaple5
	delayquarter
	ret

maple_tx_end:
	; Start of sequence: pin 1 is high, pin 5 is low.
	maple_high bitmaple1
	maple_low bitmaple5
	delayquarter
	; Pin 5 goes high for a short time.
	maple_high bitmaple5
	delayquarter
	; Pin 5 goes low
	maple_low bitmaple5
	delayquarter
	; Pin 1 goes low for 2 cycles
	maple_low bitmaple1
	RCALL delayhalf
	; Pin 1 goes high for 2 cycles
	maple_high bitmaple1
	RCALL delayhalf
	; Pin 1 goes low for 2 cycles
	maple_low bitmaple1
	RCALL delayhalf
	; Pin 1 goes high for 2 cycles.
	maple_high bitmaple1
	RCALL delayhalf
	; End of sequence: pin 5 goes high
	maple_high bitmaple5
	ret


maple_tx_phase1:
	BST r18, 7				; Read the bit
	BRTC 1f					; Is it set?
	maple_high bitmaple5	; Yes, put the bit on the wire
1:
	maple_low bitmaple1		; New data is ready
	delayquarter			; Wait for other end to notice
	maple_high bitmaple5	; Phase complete
	ret

maple_tx_phase2:
	BST r18, 7				; Read the bit
	BRTC 1f					; Is it set?
	maple_high bitmaple1	; Set it 
1:
	maple_low bitmaple5		; Notify
	delayquarter			; Wait for other end to notice
	maple_high bitmaple1	; Phase complete
	ret

; r22: length
; r23: unused
; r24: low order bit of buffer pointer
; r25: high order bit of buffer pointer
maple_tx_data:
	MOVW r26, r24				; X register <- the buffer

_maple_tx_next_byte:
	LD r18, X+					; Next byte of data into r18

	; put the byte on the bus one bit at a time.
	RCALL maple_tx_phase1		; bit 7
	LSL r18
	RCALL maple_tx_phase2		; bit 6
	LSL r18
	RCALL maple_tx_phase1		; bit 5
	LSL r18
	RCALL maple_tx_phase2		; bit 4
	LSL r18
	RCALL maple_tx_phase1		; bit 3
	LSL r18
	RCALL maple_tx_phase2		; bit 2
	LSL r18
	RCALL maple_tx_phase1		; bit 1
	LSL r18
	RCALL maple_tx_phase2		; bit 0
	
	DEC r22						; Are we done yet?
	BRNE _maple_tx_next_byte 	; No, get the next character
	
	ret

; r22: length (1 byte)
; r23: unused
; r24: low order bit of buffer pointer
; r25: high order bit of buffer pointer

; Returns pointer to final character stored in r25:r24
maple_tx_raw:
	; Set pins to output for transmission
	SBI _SFR_IO_ADDR(DDRMAPLE), bitmaple1
	SBI _SFR_IO_ADDR(DDRMAPLE), bitmaple5


	RCALL maple_tx_start
	RCALL maple_tx_data
	RCALL maple_tx_end

	; Tx over: set pins to input and enable pull-up resistors.
	SBI _SFR_IO_ADDR(PORTMAPLE), bitmaple1
	SBI _SFR_IO_ADDR(PORTMAPLE), bitmaple5
	CBI _SFR_IO_ADDR(DDRMAPLE), bitmaple1
	CBI _SFR_IO_ADDR(DDRMAPLE), bitmaple5

	ret

; Watchdog timer
.macro timer_init
	CLI

	STS TIMSK2, r1					; Normal mode (no PWM)

	STS TCCR2A, r1					; Normal mode (no PWM)

	LDI r18, 1 << CS22 | 1 << CS21 | 1 << CS20
	STS TCCR2B, r18					; Timer increments every 1024 cycles
									; and overflows every 1024 * 256 cycles,
									; or about 61 times a second at 16MHz

	STS TCNT2, r1					; Timer count

	LDI r18, 1						; TIFR2[0] -> 1 to clear
	STS TIFR2, r18					; overflow irq flag

	SEI
.endm

.macro timer_on
	LDI r18, 1 << TOIE2
	STS TIMSK2, r18
.endm

.macro timer_off
	STS TIMSK2, r1
.endm

.macro timer_reset
	STS TCNT2, r1					; Count register -> 0
.endm

; Watchdog timer interrupt routine
; When this fires, it returns to r25:r24, effectively doing
; a longjmp().
TIMER2_OVF_vect:
	IN intsave, _SFR_IO_ADDR(SREG)	; Save registers;
	
	POP intwork						; Remove the old return address
	POP intwork						; Both words
	PUSH r24						; Replace it with the new one
	PUSH r25						; Both words
	STS TIMSK2, r1					; Disable the timer

	OUT _SFR_IO_ADDR(SREG), intsave	; Restore registers
	reti

; Reading
.macro _rx_read clockbit
; Version 1:
; Worst-case scenario here: the port is set halfway through the IN -- total 
; cost is most of the IN, the BST, 2 cycles for the BRTS, plus the next IN,
; for a total of 5 cycles, which is sometimes out of tolerance.
;1:	IN rport, _SFR_IO_ADDR(PINMAPLE)	; 1
;	BST rport, \clockbit			; 1
;	BRTS 1b							; 1 (if fall through)

; Version 2:
; This works a little better because by the time we detect the falling edge
; we already have the value.
1:	IN rport, _SFR_IO_ADDR(PINMAPLE)
	SBIC _SFR_IO_ADDR(PINMAPLE), \clockbit
	RJMP 1b
.endm

.macro _rx_store reg srcbit destbit
	BST \reg, \srcbit		; 1
	BLD r18, \destbit		; 1
;1:	IN \reg, _SFR_IO_ADDR(PINMAPLE)
;	BST \reg, \srcbit
;	BRTC 1b
.endm

maple_rx_raw:
	MOVW r26, r24					; X register <- the buffer

	; Set up our bailout routine: r25:24 point to an address to "reti" to.
	ldi r25, hi8(pm(_maple_rx_raw_watchdog))
	ldi r24, lo8(pm(_maple_rx_raw_watchdog))

	LDS r18, TIMSK0					; disable Arduino interrupts
	PUSH r18						; to re-enable later
	STS TIMSK0, r1

	timer_init						; Set up our watchdog timer

	; Tell the device it can start sending data. (this is from the tx lead-out)
	; maple_high bitmaple5 

	; Wait for a start sequence
	timer_on						; rx will start soon

1:	IN rport2, _SFR_IO_ADDR(PINMAPLE)
	BST rport2, bitmaple1			; maple1
	BRTC 1b							; must be high initially

2:	IN rport2, _SFR_IO_ADDR(PINMAPLE)
	BST rport2, bitmaple1
	BRTS 2b							; must be low to continue

3:	IN rport2, _SFR_IO_ADDR(PINMAPLE)
	BST rport2, bitmaple1			; maple1
	BRTC 3b							; must be high now

	_rx_read bitmaple1
_rx_loop:
	_rx_store rport bitmaple5 7	
	_rx_read bitmaple5
	_rx_store rport bitmaple1 6
	_rx_read bitmaple1
	_rx_store rport bitmaple5 5
	_rx_read bitmaple5
	_rx_store rport bitmaple1 4
	_rx_read bitmaple1
	timer_reset						; pat the watchdog
	_rx_store rport bitmaple5 3
	_rx_read bitmaple5
	_rx_store rport bitmaple1 2
	_rx_read bitmaple1
	_rx_store rport bitmaple5 1
	_rx_read bitmaple5
	_rx_store rport bitmaple1 0	; 2
	ST X+, r18					
	_rx_read bitmaple1
	RJMP _rx_loop			

_maple_rx_raw_watchdog:				; Watchdog bailed us out. We're done!
	; debug_pin_high
	POP r18							;
	STS TIMSK0, r18					; re-enable Arduino interrupts

	MOVW r24, r26					; end of buffer <- X register

	ret

maple_timer_test:
	; Set up our bailout routine: r25:24 point to an address to "reti" to.
	ldi r25, hi8(pm(maple_timer_test_watchdog))
	ldi r24, lo8(pm(maple_timer_test_watchdog))

	; Set up the timer
	timer_init
	timer_on

1:
	nop
	rjmp 1b

maple_timer_test_watchdog:
	; Timer got us!
	timer_off

	ret;

; Turn the led on if r24 (first int parameter) is 1, off if r24 is 0.
debug:
	IN r18, _SFR_IO_ADDR(PORTB)
	bst r24, 0						; first parameter: on or off?
	bld r18, DEBUG_LED_BIT			; bit 5 on duemilanove, bit 7 on the mega
	out _SFR_IO_ADDR(PORTB), r18	; on port B
	ret

