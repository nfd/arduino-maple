#!/usr/bin/env python

import sys
import struct
import select
import serial
import time

PORT='/dev/ttyUSB0'
#PORT='/dev/tty.usbserial-A700ekGi'
#PORT = 'COM3:'

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

# Hardcoded recipient addresses.
# Controller, main peripheral, port A
ADDRESS_CONTROLLER = 1 << 5 
# Controller, first sub-peripheral, port A
ADDRESS_PERIPH1 = 1
# Dreamcast, magic value, port A
ADDRESS_DC         = 0

def log(txt):
	print txt

def debug_hex(packet):
	display = ['%02x' % (ord(item)) for item in packet]
	return ''.join(display)

def debug_txt(packet):
	display = [c if ord(c) >= ord(' ') and ord(c) <= ord('z') else '.' for c in packet]
	return ''.join(display)
	
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
	return ''.join(swapped)

def print_header(data):
	words     = ord(data[0])
	sender    = ord(data[1])
	recipient = ord(data[2])
	command   = ord(data[3])
	print "Command %x sender %x recipient %x length %x" % (command, recipient, sender, words)

def load_image(filename):
	data = [0] * (48 * 32 / 8)
	x = y = 0
	stride = 48
	lines = open(filename, 'r').readlines()
	lines = lines[-1::-1]
	for line in lines:
		while line[-1] in '\r\n':
			line = line[:-1]
		for x in range(len(line)):
			if line[x] != ' ':
				byte = (x + (y * stride)) / 8
				bit  = (x + (y * stride)) % 8
				# Magical transformations! 
				# Brilliant memory layout here
				if y % 2 == 0:
					if x < 16:
						byte += (stride / 8)
					else:
						byte -= 2
				if y % 2 == 1:
					if x < 32:
						byte += 2
					else:
						byte -= (stride / 8)

				data[byte] |= 1 << bit
		y += 1
	data = ''.join([chr(byte) for byte in data])
	assert len(data) == 48 * 32 / 8
	return data

class MapleProxy(object):
	def __init__(self):
		log("connecting to %s" % (PORT))
		self.handle = serial.Serial(PORT, 57600, timeout = 3)
		time.sleep(2) # allow it to reset
		log("connected")
	
	def __del__(self):
		if hasattr(self, 'handle'):
			self.handle.close()
	
	def deviceInfo(self, address):
		# cmd 1 = request device information
		info_bytes = self.transact(1, address, '')
		if info_bytes is None:
			print "No device found at address:"
			print hex(address)
			return

		print debug_hex(info_bytes), len(info_bytes)
		#print info_bytes, len(info_bytes)
		print_header(info_bytes[:4])
		info_bytes = info_bytes[4:] # Strip header
		#print debug_hex(info)
		func, func_data_0, func_data_1, func_data_2, product_name,\
				product_license =\
				struct.unpack("<IIII32s60s", info_bytes[:108])
		max_power, standby_power = struct.unpack(">HH", info_bytes[108:112])
		print "Device information:"
		print "Functions  :", ', '.join(decode_func_codes(func))
		print "Periph 1   :", hex(func_data_0)
		print "Periph 2   :", hex(func_data_1)
		print "Periph 3   :", hex(func_data_2)
		#print "Area       :", ord(area_code)
		#print "Direction? :", ord(connector_dir)
		print "Name       :", debug_txt(swapwords(product_name))
		print "License    :", debug_txt(swapwords(product_license))
		print "Power      :", standby_power
		print "Power max  :", max_power
	
	def writeLCD(self, address, lcddata):
		assert len(lcddata) == 192
		data = struct.pack("<II", 4, 0) + lcddata
		info_bytes = self.transact(12, address, data)
		if info_bytes is None:
			print "No response to writeLCD"
		else:
			print_header(info_bytes[:4])

	def compute_checksum(self, data):
		checksum = 0
		for datum in data:
			checksum ^= ord(datum)
		return chr(checksum)

	def transact(self, command, recipient, data):
		# Construct a frame header.
		sender = ADDRESS_DC
		assert len(data) < 256
		header = (command << 24) | (recipient << 16) | (sender << 8) | (len(data) / 4)
		packet = struct.pack("<I", header) + data
		packet += self.compute_checksum(packet)

		#print debug_hex(packet)
		# Write the frame, wait for response.
		self.handle.write(chr(len(packet)))
		self.handle.write(packet)
		num_bytes = self.handle.read(1)
		if num_bytes:
			num_bytes = ord(num_bytes)
			return self.handle.read(num_bytes)
		else:
			return None
	
def test():
	if len(sys.argv) == 2:
		image_fn = sys.argv[1]
	else:
		image_fn = 'astroboy.txt'
	image = load_image(image_fn)

	bus = MapleProxy()

	# Nothing will work before you do a deviceInfo on the controller.
	# I guess this forces the controller to enumerate its devices.
	bus.deviceInfo(ADDRESS_CONTROLLER)
	bus.deviceInfo(ADDRESS_PERIPH1)
	bus.writeLCD(ADDRESS_PERIPH1, image)

test()

