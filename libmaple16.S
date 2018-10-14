; Functions for Maple bus support on devices with 16-bit program counters (328)

#include <avr/io.h>

; reg usage faq: http://www.nongnu.org/avr-libc/user-manual/FAQ.html#faq_reg_usage
; essentially we can play with regs 18 to 27 and 30 and 31.

.global debug
.global maple_tx_raw
.global maple_rx_raw
.global maple_timer_test

#define tmp1 r18
#define tmp2 r19
#define tmp3 r20
#define rport r21

; Maple1 is on bit 0 of PORTMAPLE -- mask of 1:
#define bitmaple1 0
#define maskmaple1 1
; maple5 is on bit 1 -- mask of 10:
#define bitmaple5 1
#define maskmaple5 2
#define maskmaple 3

#define bufsize_div_four 255

#define PORTMAPLE1 PORTB
#define PINMAPLE1 PINB
#define DDRMAPLE1 DDRB

#define PORTMAPLE2 PORTC
#define PINMAPLE2 PINC
#define DDRMAPLE2 DDRC

#define IOM1 _SFR_IO_ADDR(PINMAPLE1)
#define IOM2 _SFR_IO_ADDR(PINMAPLE2)

.macro maple_high pin
	SBI _SFR_IO_ADDR(PORTMAPLE1), \pin
.endm

.macro maple_low pin
	CBI _SFR_IO_ADDR(PORTMAPLE1), \pin
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

.macro threenops
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
	; moved to rx
	;maple_high bitmaple5
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
	; Set primary pins to output for transmission
	SBI _SFR_IO_ADDR(DDRMAPLE1), bitmaple1
	SBI _SFR_IO_ADDR(DDRMAPLE1), bitmaple5

	RCALL maple_tx_start
	RCALL maple_tx_data
	RCALL maple_tx_end

	; Tx over: set pins to input and enable pull-up resistors. (Done in rx)
	;SBI _SFR_IO_ADDR(PORTMAPLE1), bitmaple1
	;CBI _SFR_IO_ADDR(DDRMAPLE1), bitmaple1
	; SBI _SFR_IO_ADDR(PORTMAPLE1), bitmaple5
	; CBI _SFR_IO_ADDR(DDRMAPLE1), bitmaple5

	ret

.macro read_four_samples
	IN r18, IOM2		; ----51-- ------51 ----51--			r18 is third read (after loop). order: r19, r20, r18
	OR r18, r19			; ----5151								r18 = none, none, third, first
	SWAP r18			; 5151----								r18 = third, first, none, none
	IN r19, IOM1		; 5151---- ------51
	OR r18, r20			; 515151--								r18 = third, first, second, none
	OR r18, r19			; 51515151								r18 = third, first, second, fourth
	IN r19, IOM1		; 51515151 ------51						r19 is new first
	ST X+, r18			; -------- ------51						 
	IN r20, IOM2		; -------- ------51 ----51--			r20 is new second
.endm

; r24:25 -- pointer to buffer
; r22:23 -- skip_amt
maple_rx_raw:
	MOVW r26, r24					; X register <- the buffer
	LDI r30, bufsize_div_four		; low byte of Z <- space remaining div 4

	LDI r18, 0						; clear r18

	; Tell the device it can start sending data. (this is from the tx lead-out)
	maple_high bitmaple5  ; done implicitly by enabling pull-ups below
	SBI _SFR_IO_ADDR(PORTMAPLE1), bitmaple1
	CBI _SFR_IO_ADDR(DDRMAPLE1), bitmaple1
	SBI _SFR_IO_ADDR(PORTMAPLE1), bitmaple5
	CBI _SFR_IO_ADDR(DDRMAPLE1), bitmaple5

	; start sequence: wait for bitmaple1 to go low
2:  SBIC _SFR_IO_ADDR(PINMAPLE1), bitmaple1
	RJMP 2b

	; wait for bitmapl1 to go high again
3:  SBIS _SFR_IO_ADDR(PINMAPLE1), bitmaple1
	RJMP 3b

	; This seems to be required here to avoid being one bit early. This
	; one-cycle NOP plus the previous (not taken, thus one-cycle) RJMP forms one
	; sample period.
	NOP

	; lead-in: read_four_samples expects r18 and r20 to be populated in this way.
	IN r19, IOM1
	NOP
	NOP
	IN r20, IOM2
	NOP
	NOP
4:
	; main read loop, unrolled 4x to read 4 bytes.

	; read first byte
	read_four_samples

	; read second byte:
	NOP
	NOP
	read_four_samples

	; read third byte:
	NOP
	NOP
	read_four_samples

	; read final byte
	DEC r30					; have we run out of space?
	BREQ _maple_rx_end		; yes, stop writing
	read_four_samples

	; lead-out: 2-cycle jump to read the next 4 bytes.
	RJMP 4b

_maple_rx_end:
	; debug_pin_high
	;POP r18							;
	;STS TIMSK0, r18					; re-enable Arduino interrupts

	MOVW r24, r26					; end of buffer <- X register

	ret

; Turn the led on if r24 (first int parameter) is 1, off if r24 is 0.
debug:
	IN r18, _SFR_IO_ADDR(PORTB)
	bst r24, 0						; first parameter: on or off?
	bld r18, DEBUG_LED_BIT			; bit 5 on duemilanove, bit 7 on the mega
	out _SFR_IO_ADDR(PORTB), r18	; on port B
	ret

