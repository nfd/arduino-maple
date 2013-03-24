# Makefile for building small AVR executables, supports C and C++ code
# Author: Kiril Zyapkov
# Hacked up by nfd

# Settings for atmega328
MMCU = atmega328
MCU = m328p
AVRDUDE_PROGRAMMER = stk500v1
UPLOAD_SPEED = -b 57600
PORT = /dev/tty.usbserial-A700ekGi

# Settings for atmega2560. NB upload speed is autodetected.
#MMCU = atmega2560
#AVRDUDE_PROGRAMMER = stk600
#MCU = m2560
#UPLOAD_SPEED=
#PORT = /dev/tty.usbmodemfa131
 
# Other settings that hopefully won't need changing much follow.
SOURCE_DIRS = . arduino
INCLUDE_DIRS = arduino
# This probably can't be changed without modifying libmaple.S.
F_CPU = 16000000UL
SRC_ROOT = .
BUILD_DIR = build
 
CFLAGS = -Wall -g2 -gstabs -Os -fpack-struct -fshort-enums -ffunction-sections \
 -fdata-sections -ffreestanding -funsigned-char -funsigned-bitfields \
 -mmcu=$(MMCU) -DF_CPU=$(F_CPU) $(INCLUDE_DIRS:%=-I$(SRC_ROOT)/%)
 
CXXFLAGS = -Wall -g2 -gstabs -Os -fpack-struct -fshort-enums -ffunction-sections \
 -fdata-sections -ffreestanding -funsigned-char -funsigned-bitfields \
 -fno-exceptions -mmcu=$(MMCU) -DF_CPU=$(F_CPU) $(INCLUDE_DIRS:%=-I$(SRC_ROOT)/%)
 
LDFLAGS = -Os -Wl,-gc-sections -mmcu=$(MMCU) #-Wl,--relax
 
TARGET = $(notdir $(realpath $(SRC_ROOT)))
CC = avr-gcc
CXX = avr-g++
OBJCOPY = avr-objcopy
OBJDUMP = avr-objdump
AR  = avr-ar
SIZE = avr-size

SRC = $(wildcard $(SOURCE_DIRS:%=$(SRC_ROOT)/%/*.c))
 
CXXSRC = $(wildcard $(SOURCE_DIRS:%=$(SRC_ROOT)/%/*.cpp))

ASMSRC = $(wildcard $(SOURCE_DIRS:%=$(SRC_ROOT)/%/*.S))
 
OBJ = $(SRC:$(SRC_ROOT)/%.c=$(BUILD_DIR)/%.o) $(CXXSRC:$(SRC_ROOT)/%.cpp=$(BUILD_DIR)/%.o) $(ASMSRC:$(SRC_ROOT)/%.S=$(BUILD_DIR)/%.o)
 
DEPS = $(OBJ:%.o=%.d)
 
$(BUILD_DIR)/%.o: $(SRC_ROOT)/%.c
	$(CC) $(CFLAGS) -c $< -o $@

$(BUILD_DIR)/%.o: $(SRC_ROOT)/%.S
	$(CC) $(CFLAGS) -c $< -o $@
 
$(BUILD_DIR)/%.o: $(SRC_ROOT)/%.cpp
	$(CXX) $(CXXFLAGS) -c $< -o $@
 
all: app.hex printsize

#$(TARGET).a: $(OBJ)
#	$(AR) rcs $(TARGET).a $?

app.elf: $(OBJ)
	$(CXX) $(LDFLAGS) $(OBJ) -o $@
 
$(BUILD_DIR)/%.d: $(SRC_ROOT)/%.c
	mkdir -p $(dir $@)
	$(CC) $(CFLAGS) -MM -MF $@ $<
 
$(BUILD_DIR)/%.d: $(SRC_ROOT)/%.cpp
	mkdir -p $(dir $@)
	$(CXX) $(CXXFLAGS) -MM -MF $@ $<
 
#$(TARGET).elf: $(TARGET).a
#	$(CXX) $(LDFLAGS) $< -o $@
 
app.hex: app.elf
	$(OBJCOPY) -R .eeprom -O ihex $<  $@
 
clean:
	$(RM) $(DEPS) $(OBJ)
 
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

