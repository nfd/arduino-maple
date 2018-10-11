#!/usr/bin/env python

import sys
import struct
import select
import serial
import time
import argparse

#PORT='/dev/ttyUSB0'    # Linux
#PORT = 'COM3:' # Windows
#PORT='/dev/tty.usbserial-A700ekGi'    # OS X (or similar)
PORT='/dev/tty.usbmodemfa131'

# Device function codes
FN_CONTROLLER  = 1
FN_MEMORY_CARD = 2
FN_LCD         = 0x4
FN_CLOCK       = 0x8
FN_MICROPHONE  = 0x10
FN_AR_GUN      = 0x20
FN_KEYBOARD    = 0x40
FN_LIGHT_GUN   = 0x80
FN_PURU_PURU   = 0x100
FN_MOUSE       = 0x200

FN_CODE_MAP    = {FN_CONTROLLER: 'CONTROLLER', FN_MEMORY_CARD: "MEMORY_CARD",
        FN_LCD: "LCD", FN_CLOCK: "CLOCK", FN_MICROPHONE: "MICROPHONE",
        FN_AR_GUN: "AR_GUN", FN_KEYBOARD: "KEYBOARD", FN_LIGHT_GUN: "LIGHT_GUN",
        FN_PURU_PURU: "PURU_PURU", FN_MOUSE: "MOUSE"}

# Device commands 
CMD_INFO          = 0x01
CMD_INFO_EXT      = 0x02
CMD_RESET         = 0x03
CMD_SHUTDOWN      = 0x04
CMD_INFO_RESP     = 0x05
CMD_INFO_EXT_RESP = 0x06
CMD_ACK_RESP      = 0x07
CMD_XFER_RESP     = 0x08
CMD_GET_COND      = 0x09
CMD_GET_MEMINFO   = 0x0A
CMD_READ          = 0x0B
CMD_WRITE         = 0x0C
CMD_WRITE_COMPLETE = 0x0D
CMD_SET_COND      = 0x0E
CMD_NO_RESP       = 0xFF
CMD_UNSUP_FN_RESP = 0xFE
CMD_UNKNOWN_RESP  = 0xFD
CMD_RESEND_RESP   = 0xFC
CMD_FILE_ERR_RESP = 0xFB


# Hardcoded recipient addresses.
# Controller, main peripheral, port A
ADDRESS_CONTROLLER = 1 << 5 
# Controller, first sub-peripheral, port A
ADDRESS_PERIPH1 = 1
# Dreamcast, magic value, port A
ADDRESS_DC         = 0

def log(txt):
    print(txt)

def debug_hex(packet):
    def ascii(b):
        return ' %c' % (b,) if 32 <= b <= 127 else '%02x' % (b,)

    #display = ['%02x %c ' % (item, ascii(item)) for item in packet]
    #return ''.join(display)
    return ''.join(ascii(item) for item in packet)

def debug_txt(packet):
    return bytes([c if int(c) >= ord(' ') and int(c) <= ord('z') else ord('.') for c in packet])
    
def decode_func_codes(code):
    names = []
    for candidate in sorted(FN_CODE_MAP.keys()):
        if code & candidate:
            names.append(FN_CODE_MAP[candidate])

    return names

def swapwords(s):
    swapped = []
    while s:
        swapped.append(s[:4][-1::-1])
        s = s[4:]
    return b''.join(swapped)

def print_header(data):
    words     = data[0]
    sender    = data[1]
    recipient = data[2]
    command   = data[3]
    print("Command %x sender %x recipient %x length %x" % (command, recipient, sender, words))

def get_command(data):
    if data:
        return data[3]
    else:
        return None

BUTTONS = ["C", "B", "A", "START", "UP", "DOWN", "LEFT", "RIGHT",
            "Z", "Y", "X", "D", "UP2", "DOWN2", "LEFT2", "RIGHT2"]
def print_controller_info(data):
    print_header(data)
    data = data[4:]  # Header
    data = data[4:]  # Func
    data = data[:-1] # CRC
    data = swapwords(data)
    buttons = struct.unpack("<H", data[:2])[0]
    buttons = ~buttons & 0xffff
    button_names = []
    for bit, name in enumerate(BUTTONS):
        if buttons & (1 << bit):
            button_names.append(name)
    print("Ltrig", data[3], end=' ')
    print("Rtrig", data[2], end=' ')
    print("Joy X", data[4], end=' ')
    print("Joy Y", data[5], end=' ')
    print("Joy X2", data[6], end=' ')
    print("Joy Y2", data[7], end=' ')
    print(", ".join(button_names))
    #print debug_hex(data)

def load_image(filename):
    data = [0] * ((48 * 32) // 8)
    x = y = 0
    stride = 48
    lines = open(filename, 'r').readlines()
    lines = lines[-1::-1]
    for line in lines:
        while line[-1] in '\r\n':
            line = line[:-1]
        for x in range(len(line)):
            if line[x] != ' ':
                byte = (x + (y * stride)) // 8
                bit  = (x + (y * stride)) % 8
                # Magical transformations! 
                # Brilliant memory layout here
                if y % 2 == 0:
                    if x < 16:
                        byte += (stride // 8)
                    else:
                        byte -= 2
                if y % 2 == 1:
                    if x < 32:
                        byte += 2
                    else:
                        byte -= (stride // 8)

                data[byte] |= 1 << bit
        y += 1
    assert len(data) == 48 * 32 // 8
    return bytes(data)

def debittify(bitstring):
    """
    The maple proxy sends a bitstring consisting of the state of the two pins sampled at 2MSPS. Decode these 
    back into bytes.
    """
    #print('prebit', debug_hex(bitstring))
    # the two bits are (maple5, maple1) and are stored in each byte in this way:
    # 51515151
    def iter_bits():
        # first byte: three bits
        first = bitstring[0]
        yield(first & 0x80, first & 0x40)
        yield(first & 0x20, first & 0x10)
        yield(first & 0x2, first & 0x1)
        for byte in bitstring[1:]:
            yield(byte & 0x8, byte & 0x4)
            yield(byte & 0x80, byte & 0x40)
            yield(byte & 0x20, byte & 0x10)
            yield(byte & 0x2, byte & 0x1)

    output = []
    accum = 0
    bitcount = 0

    def add_bit(thebit):
        nonlocal accum, bitcount, output
        if bitcount == 8:
            output.append(accum)
            bitcount = accum = 0

        accum <<= 1
        if thebit:
            accum |= 1
        bitcount += 1

    state = 0
    for pin5, pin1 in iter_bits():
        if state == 0 and not pin1:
            add_bit(pin5)
            state = 1
        elif state == 1 and pin5:
            state = 2
        elif state == 2 and not pin5:
            add_bit(pin1)
            state = 3
        elif state == 3 and pin1:
            state = 0

    output.append(accum)

    #print('debit', '{0:08b}{1:08b}{2:08b}{3:08b}'.format(output[0], output[1], output[2], output[3]))
    return bytes(output)

class MapleProxy(object):
    def __init__(self, port=PORT):
        log("connecting to %s" % (port))
        self.handle = serial.Serial(port, 57600, timeout = 1)

        total_sleep = 0
        while total_sleep < 5:
            print("are you there?")
            self.handle.write(b'\x00') # are-you-there
            result = self.handle.read(1)
            if result == b'\x01':
                break
            time.sleep(0.5)
            total_sleep += 0.5
        else:
            raise Exception()

        print("maple proxy detected")
    
    def __del__(self):
        if hasattr(self, 'handle'):
            self.handle.close()
    
    def deviceInfo(self, address):
        # cmd 1 = request device information
        info_bytes = self.transact(CMD_INFO, address, b'')
        if not info_bytes:
            print("No device found at address:")
            print(hex(address))
            return False

        #print info_bytes, len(info_bytes)
        print_header(info_bytes[:4])
        info_bytes = info_bytes[4:] # Strip header
        print("Device information:")
        print("raw:", debug_hex(swapwords(info_bytes)), len(info_bytes))
        func, func_data_0, func_data_1, func_data_2, product_name,\
                product_license =\
                struct.unpack("<IIII32s60s", info_bytes[:108])
        max_power, standby_power = struct.unpack(">HH", info_bytes[108:112])
        print("Functions  :", ', '.join(decode_func_codes(func)))
        print("Periph 1   :", hex(func_data_0))
        print("Periph 2   :", hex(func_data_1))
        print("Periph 3   :", hex(func_data_2))
        #print "Area       :", ord(area_code)
        #print "Direction? :", ord(connector_dir)
        print("Name       :", debug_txt(swapwords(product_name)))
        print("License    :", debug_txt(swapwords(product_license)))
        # These are in tenths of a milliwatt, according to the patent:
        print("Power      :", standby_power)
        print("Power max  :", max_power)
        return True
    
    def getCond(self, address, function):
        data = struct.pack("<I", function)
        info_bytes = self.transact(CMD_GET_COND, address, data)
        print("getCond:")
        print_header(info_bytes[:4])
        print(debug_hex(info_bytes))
    
    def writeLCD(self, address, lcddata):
        assert len(lcddata) == 192
        data = struct.pack("<II", FN_LCD, 0) + lcddata
        info_bytes = self.transact(CMD_WRITE, address, data)
        if info_bytes is None:
            print("No response to writeLCD")
        else:
            print_header(info_bytes[:4])
    
    def writeFlash(self, address, block, phase, data):
        data = swapwords(data)
        assert len(data) == 128
        addr = (phase << 16) | block
        data = struct.pack("<II", FN_MEMORY_CARD, addr) + data
        info_bytes = self.transact(CMD_WRITE, address, data)
        print(info_bytes)
        return

        if info_bytes is None:
            print("No response to writeFlash")
        else:
            assert get_command(info_bytes) == CMD_ACK_RESP, get_command(info_bytes)

    def writeFlashComplete(self, address, block):
        addr = (4 << 16) | block
        data = struct.pack('<II', FN_MEMORY_CARD, addr)
        info_bytes = self.transact(CMD_WRITE_COMPLETE, address, data)
        print(info_bytes)
        return

    def readFlash(self, address, block, phase):
        addr = (0 << 24) | (phase << 16) | block
        data = struct.pack("<II", FN_MEMORY_CARD, addr)
        info_bytes = self.transact(CMD_READ, address, data)
        assert get_command(info_bytes) == CMD_XFER_RESP
        data = info_bytes[12:-1]
        data = swapwords(data)
        return data
    
    def resetDevice(self, address):
        info_bytes = self.transact(CMD_RESET, address, b'')
        print_header(info_bytes[:4])
        print(debug_hex(info_bytes))
    
    def getMemInfo(self, address):
        partition = 0x0
        data = struct.pack("<II", FN_MEMORY_CARD, partition << 24)
        info_bytes = self.transact(CMD_GET_MEMINFO, address, data)
        print_header(info_bytes[:4])
        return
        
        info_bytes = info_bytes[4:-1]
        assert len(info_bytes) == 4 + (12 * 2)
        info_bytes = swapwords(info_bytes)

        func_code, maxblk, minblk, infpos, fatpos, fatsz, dirpos, dirsz, icon, datasz,  \
            res1, res2, res3 = struct.unpack("<IHHHHHHHHHHHH", info_bytes)
        print("  Max block :", maxblk)
        print("  Min block :", minblk)
        print("  Inf pos   :", infpos)
        print("  FAT pos   :", fatpos)
        print("  FAT size  :", fatsz)
        print("  Dir pos   :", dirpos)
        print("  Dir size  :", dirsz)
        print("  Icon      :", icon)
        print("  Data size :", datasz)
    
    def readController(self, address):
        data = struct.pack("<I", FN_CONTROLLER)
        info_bytes = self.transact(CMD_GET_COND, address, data)
        return info_bytes
        #print debug_hex(info_bytes)

    def compute_checksum(self, data):
        checksum = 0
        for datum in data:
            checksum ^= datum
        return checksum

    def transact(self, command, recipient, data):
        # Construct a frame header.
        sender = ADDRESS_DC
        assert len(data) < 256
        header = (command << 24) | (recipient << 16) | (sender << 8) | (len(data) // 4)
        packet = struct.pack("<I", header) + data
        packet += bytes([self.compute_checksum(packet)])

        #print ('out', debug_hex(packet))
        # Write the frame, wait for response.
        self.handle.write(bytes([len(packet)]))
        self.handle.write(packet)
        num_bytes = self.handle.read(2)
        if num_bytes:
            num_bytes = struct.unpack(">H", num_bytes)[0]
            return debittify(self.handle.read(num_bytes))
        else:
            return None
    
def test():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', default=PORT)
    parser.add_argument('image', nargs='?', default='astroboy.txt')
    args = parser.parse_args()

    image = load_image(args.image)

    bus = MapleProxy(args.port)

    # Nothing will work before you do a deviceInfo on the controller.
    # I guess this forces the controller to enumerate its devices.
    found_controller = bus.deviceInfo(ADDRESS_CONTROLLER)
    if not found_controller:
        print("Couldn't find controller.")
        #return

    found_vmu = bus.deviceInfo(ADDRESS_PERIPH1)
    #if found_vmu:
    bus.writeLCD(ADDRESS_PERIPH1, image)

    print("Play with the controller. Hit ctrl-c when done.")
    while 1:
        print_controller_info(bus.readController(ADDRESS_CONTROLLER))
        time.sleep(1)

if __name__ == '__main__':
    test()

