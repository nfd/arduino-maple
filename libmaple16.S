; Functions for Maple bus support on devices with 16-bit program counters (328)

#include <avr/io.h>

; reg usage faq: http://www.nongnu.org/avr-libc/user-manual/FAQ.html#faq_reg_usage
; essentially we can play with regs 18 to 27 and 30 and 31.

.global debug
.global maple_tx_raw
.global maple_rx_raw
.global maple_timer_test

#define intsave r31
#define intwork r20
#define tmp1 r18
#define tmp2 r19
#define rport r21

; Maple1 is on bit 0 of PORTMAPLE -- mask of 1:
#define bitmaple1 0
#define maskmaple1 1
; maple5 is on bit 1 -- mask of 10:
#define bitmaple5 1
#define maskmaple5 2
#define maskmaple 3

#define bufsize_div_four 255

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
	; Set pins to output for transmission
	SBI _SFR_IO_ADDR(DDRMAPLE), bitmaple1
	SBI _SFR_IO_ADDR(DDRMAPLE), bitmaple5


	RCALL maple_tx_start
	RCALL maple_tx_data
	RCALL maple_tx_end

	; Tx over: set pins to input and enable pull-up resistors. (Done in rx)
	;SBI _SFR_IO_ADDR(PORTMAPLE), bitmaple1
	;CBI _SFR_IO_ADDR(DDRMAPLE), bitmaple1
	; SBI _SFR_IO_ADDR(PORTMAPLE), bitmaple5
	; CBI _SFR_IO_ADDR(DDRMAPLE), bitmaple5

	ret

maple_rx_raw:
	MOVW r26, r24					; X register <- the buffer
	LDI r30, bufsize_div_four		; low byte of Z <- space remaining div 4

	LDI r18, 0						; clear r18

	; Tell the device it can start sending data. (this is from the tx lead-out)
	;maple_high bitmaple5  ; done implicitly by enabling pull-ups below
	SBI _SFR_IO_ADDR(PORTMAPLE), bitmaple1
	CBI _SFR_IO_ADDR(DDRMAPLE), bitmaple1
	SBI _SFR_IO_ADDR(PORTMAPLE), bitmaple5
	CBI _SFR_IO_ADDR(DDRMAPLE), bitmaple5

	; Wait for a start sequence
1:  SBIS _SFR_IO_ADDR(PINMAPLE), bitmaple1
	RJMP 1b

2:  SBIC _SFR_IO_ADDR(PINMAPLE), bitmaple1
	RJMP 2b

3:  SBIS _SFR_IO_ADDR(PINMAPLE), bitmaple1
	RJMP 3b

	; first byte will be 		00 11 -- 22
	; subsequent bytes will be	11 22 00 33
4:
	IN rport, _SFR_IO_ADDR(PINMAPLE)	; (1) 					
	SWAP r18							; (1) r18 = -- 00 -- --		first: r18 = -- -- -- --
	OR r18, rport						; (1) r18 = -- 00 -- 11		first: r18 = -- -- -- 00
	LSL r18								; (1)
	IN rport, _SFR_IO_ADDR(PINMAPLE)	; (1) 
	LSL r18								; (1) r18 = 00 -- 11 --		first: r18 = -- -- 00 --

	OR r18, rport						; (1) r18 = 00 -- 11 22		first: r18 = -- -- 00 11
	SWAP r18							; (1) r18 = 11 22 00 --		first: r18 = 00 11 -- --

	IN rport, _SFR_IO_ADDR(PINMAPLE)	; (1)
	OR r18, rport						; (1) r18 = 11 22 00 33		first: r18 = 00 11 -- 22
	ST X+, r18							; (2)

	IN r18, _SFR_IO_ADDR(PINMAPLE)		; (1) r18 = -- -- -- 00

	; unroll 1
	NOP
	NOP
	NOP

	IN rport, _SFR_IO_ADDR(PINMAPLE)	; (1) 					
	SWAP r18							; (1) r18 = -- 00 -- --		first: r18 = -- -- -- --
	OR r18, rport						; (1) r18 = -- 00 -- 11		first: r18 = -- -- -- 00
	LSL r18								; (1)
	IN rport, _SFR_IO_ADDR(PINMAPLE)	; (1) 
	LSL r18								; (1) r18 = 00 -- 11 --		first: r18 = -- -- 00 --

	OR r18, rport						; (1) r18 = 00 -- 11 22		first: r18 = -- -- 00 11
	SWAP r18							; (1) r18 = 11 22 00 --		first: r18 = 00 11 -- --

	IN rport, _SFR_IO_ADDR(PINMAPLE)	; (1)
	OR r18, rport						; (1) r18 = 11 22 00 33		first: r18 = 00 11 -- 22
	ST X+, r18							; (2)

	IN r18, _SFR_IO_ADDR(PINMAPLE)		; (1) r18 = -- -- -- 00

	; unroll 2
	NOP
	NOP
	NOP

	IN rport, _SFR_IO_ADDR(PINMAPLE)	; (1) 					
	SWAP r18							; (1) r18 = -- 00 -- --		first: r18 = -- -- -- --
	OR r18, rport						; (1) r18 = -- 00 -- 11		first: r18 = -- -- -- 00
	LSL r18								; (1)
	IN rport, _SFR_IO_ADDR(PINMAPLE)	; (1) 
	LSL r18								; (1) r18 = 00 -- 11 --		first: r18 = -- -- 00 --

	OR r18, rport						; (1) r18 = 00 -- 11 22		first: r18 = -- -- 00 11
	SWAP r18							; (1) r18 = 11 22 00 --		first: r18 = 00 11 -- --

	IN rport, _SFR_IO_ADDR(PINMAPLE)	; (1)
	OR r18, rport						; (1) r18 = 11 22 00 33		first: r18 = 00 11 -- 22
	ST X+, r18							; (2)

	IN r18, _SFR_IO_ADDR(PINMAPLE)		; (1) r18 = -- -- -- 00

	; unroll 3
	NOP
	NOP
	NOP

	IN rport, _SFR_IO_ADDR(PINMAPLE)	; (1) 					
	SWAP r18							; (1) r18 = -- 00 -- --		first: r18 = -- -- -- --
	OR r18, rport						; (1) r18 = -- 00 -- 11		first: r18 = -- -- -- 00
	LSL r18								; (1)
	IN rport, _SFR_IO_ADDR(PINMAPLE)	; (1) 
	LSL r18								; (1) r18 = 00 -- 11 --		first: r18 = -- -- 00 --

	OR r18, rport						; (1) r18 = 00 -- 11 22		first: r18 = -- -- 00 11
	SWAP r18							; (1) r18 = 11 22 00 --		first: r18 = 00 11 -- --

	IN rport, _SFR_IO_ADDR(PINMAPLE)	; (1)
	OR r18, rport						; (1) r18 = 11 22 00 33		first: r18 = 00 11 -- 22
	ST X+, r18							; (2)

	IN r18, _SFR_IO_ADDR(PINMAPLE)		; (1) r18 = -- -- -- 00

	DEC r30								; (1)
	BRNE 4b								; (2)
	; out of space

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

