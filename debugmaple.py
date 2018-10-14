#!/usr/bin/env python
# copy of large chunks of maple.py for debug / testing purposes.
import sys
import struct
import select
import serial
import time
import argparse

PORT='/dev/tty.usbserial-A700ekGi'    # OS X (or similar)
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

log = print

def debug_hex(packet):
    def ascii(b):
        return ' %c' % (b,) if 32 <= b <= 127 else '%02x' % (b,)

    #display = ['%02x %c ' % (item, ascii(item)) for item in packet]
    #return ''.join(display)
    return ''.join(ascii(item) for item in packet)

def debug_txt(packet):
    return bytes([c if int(c) >= ord(' ') and int(c) <= ord('z') else ord('.') for c in packet])

def print_header(data):
    words     = data[0]
    sender    = data[1]
    recipient = data[2]
    command   = data[3]
    print("Command %x sender %x recipient %x length %x" % (command, recipient, sender, words))

def swapwords(s):
    swapped = []
    while s:
        swapped.append(s[:4][-1::-1])
        s = s[4:]
    return b''.join(swapped)

def decode_func_codes(code):
    names = []
    for candidate in sorted(FN_CODE_MAP.keys()):
        if code & candidate:
            names.append(FN_CODE_MAP[candidate])

    return names

def debittify(bitstring):
    """
    The maple proxy sends a bitstring consisting of the state of the two pins sampled at 2MSPS. Decode these 
    back into bytes.
    """
    def iter_bits():
        # Order of bits: 33 11 22 44
        for byte in bitstring:
            yield(byte & 0x20, byte & 0x10)
            yield(byte & 0x8, byte & 0x4)
            yield(byte & 0x80, byte & 0x40)
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
        return bitcount == 8

    state = 0
    idx = 0
    old_pin1 = 1
    old_pin5 = 0
    started = True
    debug_bits_list = []
    skip = 0
    for pin5, pin1 in iter_bits():
        if skip:
            skip -= 1
            continue

        debug_bits = '%c%c' % ('1' if pin5 else '0', '1' if pin1 else '0')

        if pin1 and pin5 and started:
            # Skip the initial both-lines-high condition
            continue

        started = False

        debug_this_time = [debug_bits]

        if old_pin1 and not pin1:
            debug_this_time.append(1)
            added = add_bit(pin5)
            if added:
                debug_this_time.append(accum)
        if old_pin5 and not pin5:
            debug_this_time.append(5)
            added = add_bit(pin1)
            if added:
                debug_this_time.append(accum)

        old_pin5 = pin5
        old_pin1 = pin1

        debug_bits_list.append(debug_this_time)

    # debug:
    for offset in range(0, len(debug_bits_list), 60):
        end = min(offset + 60, len(debug_bits_list))

        for i in range(offset, end):
            sys.stdout.write('%s ' % (debug_bits_list[i][0]))

        sys.stdout.write('\n')

        for i in range(offset, end):
            if len(debug_bits_list[i]) >= 2:
                sys.stdout.write('%s ' % ('^c' if debug_bits_list[i][1] == 1 else 'c^'))
            else:
                sys.stdout.write('   ')

        sys.stdout.write('\n')

        for i in range(offset, end):
            if len(debug_bits_list[i]) == 3:
                character = debug_bits_list[i][2]
                sys.stdout.write(' %c ' % (character,) if 32 <= character < 128 else '%02x ' % (character,))
            else:
                sys.stdout.write('   ')

        sys.stdout.write('\n')

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
    
    def deviceInfo(self, address, debug_filename=None):
        # cmd 1 = request device information
        info_bytes = self.transact(CMD_INFO, address, b'', debug_write_filename=debug_filename)
        if not info_bytes:
            print("No device found at address:")
            print(hex(address))
            return False

        #print info_bytes, len(info_bytes)
        print_header(info_bytes[:4])
        info_bytes = info_bytes[4:] # Strip header
        print("Device information:")
        print("raw:", debug_hex(swapwords(info_bytes)), len(info_bytes))
        return True
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

    def transact(self, command, recipient, data, debug_write_filename):
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
            raw_response = self.handle.read(num_bytes)
            if debug_write_filename:
                with open(debug_write_filename, 'wb') as h:
                    h.write(raw_response)
            return debittify(raw_response)
        else:
            return None

    def compute_checksum(self, data):
        checksum = 0
        for datum in data:
            checksum ^= datum
        return checksum

def debug_dump(filename):
    with open(filename, 'rb') as h:
        raw_data = h.read()

    result = debittify(raw_data)
    print("raw:", debug_hex(swapwords(result)), len(result))

def test():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', default=None)
    parser.add_argument('-d', '--debug-prefix', default=None)
    args = parser.parse_args()

    if args.port:
        bus = MapleProxy(args.port)

        # Nothing will work before you do a deviceInfo on the controller.
        # I guess this forces the controller to enumerate its devices.
        debug_filename = '%s-controller' % (args.debug_prefix,) if args.debug_prefix else None
        found_controller = bus.deviceInfo(ADDRESS_CONTROLLER, debug_filename=debug_filename)
        found_controller = bus.deviceInfo(ADDRESS_CONTROLLER, debug_filename=debug_filename)
        if not found_controller:
            print("Couldn't find controller.")
            #return

        debug_filename = '%s-vmu' % (args.debug_prefix,) if args.debug_prefix else None
        #found_vmu = bus.deviceInfo(ADDRESS_PERIPH1, debug_filename=debug_filename)
    else:
        debug_dump(args.debug_prefix + '-controller')

if __name__ == '__main__':
    test()
