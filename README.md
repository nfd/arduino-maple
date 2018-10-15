Wiring
------
You need to connect the red and white wires (clock and data lines) to two separate ports. I used a breadboard for this, but you could also just solder an extra wire on.

* Red wire:
	PORTB0 (Pin 8 on Duemilanove)
	PORTC2 (Analogue Pin 2 on Duemilanove)
* White wire:
	PORTB1 (Pin 9 on Duemilanove)
	PORTC3 (Analogue Pin 3 on Duemilanove)
* Blue wire: +5V
* GND (unshielded): GND

Converting images
-----------------
To display images using the vmu_image program, produce a 48x32 text file with 'x' where you want the set pixels to be. I use imagmagick and go through pgm using this pipeline, which is not pretty but works:

convert mypic.png pgm: |python3 pgmtotxt.py - >mypic.txt
