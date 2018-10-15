#!/usr/bin/env python
# copy of large chunks of maple.py for debug / testing purposes.
import sys
import struct
import select
import serial
import time
import argparse
import collections

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

# At least this many trailing samples must have both pins high in order for the receive to be
# considered complete.
IDLE_SAMPLES_INDICATING_COMPLETION = 8

SKIP_LOOP_LENGTH = 2  # size is given in samples

# Safety factor for skip loop to give us a chance to align subsequences -- turns out not to be needed
RX_SKIP_SAFETY_FACTOR = 0  # samples

# Number of samples stored per byte.
RAW_SAMPLES_PER_BYTE = 4

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

def get_command(data):
    if data:
        return data[3]
    else:
        return None

def decode_func_codes(code):
    names = []
    for candidate in sorted(FN_CODE_MAP.keys()):
        if code & candidate:
            names.append(FN_CODE_MAP[candidate])

    return names

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
    if hasattr(filename, 'readlines'):
        # Treat it as a handle
        lines = filename.readlines()
    else:
        with open(filename, 'r') as handle:
            lines = handle.readlines()

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

# result = decoded data
# num_samples = number of useful (bit-generating) samples
# recv_completed = no data cut off due to space constraints
DecodedRx = collections.namedtuple('DecodedRx', ('result', 'num_samples', 'completed'))
def debittify(bitstring):
    """
    The maple proxy sends a bitstring consisting of the state of the two pins sampled at 2MSPS. Decode these 
    back into bytes.
    
    We also want a sample count back from this, so return a DecodedRx.
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
        accum <<= 1
        if thebit:
            accum |= 1
        bitcount += 1

        if bitcount == 8:
            output.append(accum)
            bitcount = accum = 0

        return bitcount == 0

    state = 0
    idx = 0
    old_pin1 = 1
    old_pin5 = 0
    started = True
    debug_bits_list = []
    num_samples_all_high = 0  # in a row
    samples_this_byte = 0  # useful at the end for calculating total number of samples.
    for pin5, pin1 in iter_bits():
        debug_bits = '%c%c' % ('1' if pin5 else '0', '1' if pin1 else '0')

        if pin1 and pin5:
            if started:
                # Skip the initial both-lines-high condition
                continue
            else:
                num_samples_all_high += 1
        else:
            num_samples_all_high = 0


        started = False
        debug_this_time = [debug_bits]

        added = False
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

        if added:
            debug_this_time.append(accum)

        if added:
            samples_this_byte = 0
        else:
            samples_this_byte += 1

        old_pin5 = pin5
        old_pin1 = pin1

        debug_bits_list.append(debug_this_time)

    # debug:
    debug = False
    if debug:
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
        print('bitcount', bitcount)

    # the recv was completed if at least the last IDLE_SAMPLES_INDICATING_COMPLETION samples
    # are all '11'.
    recv_completed = num_samples_all_high >= IDLE_SAMPLES_INDICATING_COMPLETION

    if recv_completed:
        # TODO: why?
        output = output[:-1]

    num_samples = (len(bitstring) * RAW_SAMPLES_PER_BYTE) - samples_this_byte
    return DecodedRx(result=bytes(output), num_samples=num_samples, completed=recv_completed)

def align_messages(prev, current):
    return prev + current

def calculate_recv_skip(samples_so_far):
    " Calculate the amount to skip forward. "
    samples_to_skip = max(0, samples_so_far - RX_SKIP_SAFETY_FACTOR)
    return samples_to_skip // SKIP_LOOP_LENGTH

class MapleProxy(object):
    def __init__(self, port=PORT):
        log("connecting to %s" % (port))
        self.handle = serial.Serial(port, 57600, timeout = 1)

        total_sleep = 0
        while total_sleep < 5:
            print("are you there?")
            self.handle.write(b'\x00\x00\x00') # are-you-there
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
        info_bytes = self.transact(CMD_INFO, address, b'', debug_write_filename=debug_filename, allow_repeats=True)
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

    def readFlash(self, address, block, phase):
        addr = (0 << 24) | (phase << 16) | block
        cmd = struct.pack("<II", FN_MEMORY_CARD, addr)
        while True:
            info_bytes = self.transact(CMD_READ, address, cmd, None, allow_repeats=True)
            data = info_bytes[12:]
            data = swapwords(data)
            if len(data) == 512 and get_command(info_bytes) == CMD_XFER_RESP:
                break

        return data

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

    def resetDevice(self, address):
        info_bytes = self.transact(CMD_RESET, address, b'')
        print_header(info_bytes[:4])
        print(debug_hex(info_bytes))
    
    def getMemInfo(self, address):
        partition = 0x0
        data = struct.pack("<II", FN_MEMORY_CARD, partition << 24)
        info_bytes = self.transact(CMD_GET_MEMINFO, address, data, allow_repeats=True)
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

    def transact(self, command, recipient, data, debug_write_filename=None, allow_repeats=False):
        # Construct a frame header.
        sender = ADDRESS_DC
        assert len(data) < 256, data
        header = (command << 24) | (recipient << 16) | (sender << 8) | (len(data) // 4)
        packet = struct.pack("<I", header) + data
        packet += bytes([self.compute_checksum(packet)])

        #print ('out', debug_hex(packet))
        # Write the frame, wait for response.
        completed = False
        entire_message = b''
        samples_so_far = 0

        while True:
            recv_skip = calculate_recv_skip(samples_so_far)
            rx_response = self._transact_multiple(packet, recv_skip, num_tries=3 if allow_repeats else 1)
            entire_message = align_messages(entire_message, rx_response.result)
            if not allow_repeats or rx_response.completed:
                break
            samples_so_far += rx_response.num_samples

        return entire_message

    def _transact_multiple(self, packet, recv_skip, num_tries, debug_write_filename=None):
        prev_response = None
        response = None
        for retry in range(num_tries):
            self.handle.write(bytes([len(packet)]))
            self.handle.write(struct.pack('<H', recv_skip))  # recv skip
            self.handle.write(packet)
            num_bytes = self.handle.read(2)
            if num_bytes:
                num_bytes = struct.unpack(">H", num_bytes)[0]
                raw_response = self.handle.read(num_bytes)
                if debug_write_filename:
                    with open(debug_write_filename, 'wb') as h:
                        h.write(raw_response)

                response = debittify(raw_response)
                if prev_response and prev_response.result == response.result:
                    break

        return response
                
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
        if not found_controller:
            print("Couldn't find controller.")
            #return

        debug_filename = '%s-vmu' % (args.debug_prefix,) if args.debug_prefix else None
        found_vmu = bus.deviceInfo(ADDRESS_PERIPH1, debug_filename=debug_filename)
    else:
        debug_dump(args.debug_prefix + '-controller')

if __name__ == '__main__':
    test()
