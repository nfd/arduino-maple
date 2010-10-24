import os
import sys
import maple

NUM_BLOCKS = 256

def read_vmu(handle):
	bus = maple.MapleProxy()

	# Quick bus enumeration
	bus.deviceInfo(maple.ADDRESS_CONTROLLER)
	bus.deviceInfo(maple.ADDRESS_PERIPH1)

	bus.getCond(maple.ADDRESS_CONTROLLER, maple.FN_CONTROLLER)
	bus.getCond(maple.ADDRESS_PERIPH1, maple.FN_CLOCK)
	bus.getMemInfo(maple.ADDRESS_PERIPH1)

	for block_num in range(NUM_BLOCKS):
		sys.stdout.write('.')
		sys.stdout.flush()
		data = bus.readFlash(maple.ADDRESS_PERIPH1, 0, 0)
		handle.write(data)

if __name__ == '__main__':
	handle = open(sys.argv[1], 'wb')
	read_vmu(handle)
	handle.close()
	sys.exit(0)


