# Makefile for building small AVR executables, supports C and C++ code
# Author: Kiril Zyapkov
# Hacked up by nfd

# Settings for atmega328
#MMCU = atmega328
#MCU = m328p
#AVRDUDE_PROGRAMMER = stk500v1
#UPLOAD_SPEED = -b 57600
#PORT = /dev/tty.usbserial-A700ekGi
#DEBUG_LED_BIT = 5
#CHIP_SPECIFIC_ASM=libmaple16.S

# Settings for atmega2560. NB upload speed is autodetected.
MMCU = atmega2560
AVRDUDE_PROGRAMMER = stk600
MCU = m2560
UPLOAD_SPEED=
PORT = /dev/tty.usbmodemfa131
DEBUG_LED_BIT = 7
CHIP_SPECIFIC_ASM=libmaple22.S
 
# Other settings that hopefully won't need changing much follow.
SOURCE_DIRS = .
# This probably can't be changed without modifying libmaple.S.
F_CPU = 16000000UL
BUILD_DIR = build
 
CFLAGS = -Wall -g2 -gstabs -Os -fpack-struct -fshort-enums -ffunction-sections \
 -fdata-sections -ffreestanding -funsigned-char -funsigned-bitfields \
 -mmcu=$(MMCU) -DF_CPU=$(F_CPU) -DDEBUG_LED_BIT=$(DEBUG_LED_BIT)
 
CXXFLAGS = -Wall -g2 -gstabs -Os -fpack-struct -fshort-enums -ffunction-sections \
 -fdata-sections -ffreestanding -funsigned-char -funsigned-bitfields \
 -fno-exceptions -mmcu=$(MMCU) -DF_CPU=$(F_CPU) -DDEBUG_LED_BIT=$(DEBUG_LED_BIT)
 
LDFLAGS = -Os -Wl,-gc-sections -mmcu=$(MMCU) #-Wl,--relax
 
CC = avr-gcc
CXX = avr-g++
OBJCOPY = avr-objcopy
OBJDUMP = avr-objdump
AR  = avr-ar
SIZE = avr-size

SRC = $(wildcard *.c)
 
CXXSRC = $(wildcard *.cpp)

ASMSRC = libmaplecommon.S $(CHIP_SPECIFIC_ASM)
 
OBJ = $(SRC:%.c=$(BUILD_DIR)/%.o) $(CXXSRC:%.cpp=$(BUILD_DIR)/%.o) $(ASMSRC:%.S=$(BUILD_DIR)/%.o)
 
DEPS = $(OBJ:%.o=%.d)
 
$(BUILD_DIR)/%.o: ./%.c
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/%.o: ./%.S
	$(CC) $(CFLAGS) -c $< -o $@
 
$(BUILD_DIR)/%.o: ./%.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@
 
all: app.hex printsize

#$(TARGET).a: $(OBJ)
#	$(AR) rcs $(TARGET).a $?

app.elf: $(OBJ)
	$(CXX) $(LDFLAGS) $(OBJ) -o $@
 
$(BUILD_DIR)/%.d: ./%.c
	mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -MM -MF $@ $<
 
$(BUILD_DIR)/%.d: ./%.cpp
	mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) -MM -MF $@ $<
 
#$(TARGET).elf: $(TARGET).a
#	$(CXX) $(LDFLAGS) $< -o $@
 
app.hex: app.elf
	$(OBJCOPY) -R .eeprom -O ihex $<  $@
 
clean:
	$(RM) $(BUILD_DIR)/*
	rm app.*
 
printsize:
	avr-size --format=avr --mcu=$(MMCU) app.elf



# Programming support using avrdude. Settings and variables.
#PORT = /dev/ttyUSB0
AVRDUDE_PORT = $(PORT)
AVRDUDE_WRITE_FLASH = -U flash:w:app.hex
#AVRDUDE_FLAGS = -V -F -C \app\arduino-0021\hardware\tools\avr\etc\avrdude.conf 
AVRDUDE_FLAGS = -V -F \
-p $(MCU) -P $(AVRDUDE_PORT) -c $(AVRDUDE_PROGRAMMER) \
$(UPLOAD_SPEED)
#
# Program the device.
INSTALL_DIR = \app\arduino-0021
AVRDUDE = avrdude
upload: app.hex
	python pulsedtr.py $(PORT)
	$(AVRDUDE) $(AVRDUDE_FLAGS) $(AVRDUDE_WRITE_FLASH)

