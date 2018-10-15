Wiring
------

* Red wire: PORTB0 (Pin 8 on Duemilanove; Pin 53 on Mega)
* White wire: PORTB1 (Pin 9 on Duemilanove; Pin 52 on Mega)
* Blue wire: +5V
* GND (unshielded): GND

Converting images
-----------------
To display images using the vmu_image program, produce a 48x32 text file with 'x' where you want the set pixels to be. I use imagmagick and go through pgm using this pipeline, which is not pretty but works:

convert mypic.png pgm: |python3 pgmtotxt.py - >mypic.txt
