import os
import sys
import maple

DUMP_SIZE = 128 * 1024
WRITE_SIZE = 128
BLOCK_SIZE = 512

def write_vmu(handle):
	bus = maple.MapleProxy()
	
	# Quick bus enumeration
	bus.deviceInfo(maple.ADDRESS_CONTROLLER)
	bus.deviceInfo(maple.ADDRESS_PERIPH1)

	bus.getMemInfo(maple.ADDRESS_PERIPH1)

	print "Writing 256 blocks..."
	for block_num in range(DUMP_SIZE / BLOCK_SIZE):
		sys.stdout.write('.')
		sys.stdout.flush()
		orig_data = bus.readFlash(maple.ADDRESS_PERIPH1, block_num, 0)
		target_data = handle.read(BLOCK_SIZE)
		if orig_data != target_data:
			for phase_num in range(BLOCK_SIZE / WRITE_SIZE):
				#print block_num, phase_num
				data = target_data[phase_num * WRITE_SIZE : (phase_num + 1) * WRITE_SIZE]
				bus.writeFlash(maple.ADDRESS_PERIPH1, block_num, phase_num, data)
			new_data = bus.readFlash(maple.ADDRESS_PERIPH1, block_num, 0)
			if new_data != target_data:
				print "Problem: data mis-match"
				print maple.debug_hex(target_data)
				print maple.debug_hex(new_data)
				return
	
	print
	# Do a dummy read of one block to turn off the transferring-data icon
	bus.readFlash(maple.ADDRESS_PERIPH1, 0, 0)

def read_vmu():
	bus = maple.MapleProxy()

	# Quick bus enumeration
	bus.deviceInfo(maple.ADDRESS_CONTROLLER)
	bus.deviceInfo(maple.ADDRESS_PERIPH1)

	bus.getCond(maple.ADDRESS_CONTROLLER, maple.FN_CONTROLLER)
	bus.getCond(maple.ADDRESS_PERIPH1, maple.FN_CLOCK)
	bus.getMemInfo(maple.ADDRESS_PERIPH1)

	print bus.readFlash(maple.ADDRESS_PERIPH1, 0, 0)


def open_vmu_dump(fn):
	# Filename must be 128k and openable
	try:
		file_size = os.path.getsize(fn)
	except os.error:
		print >>sys.stderr, "Can't access %s" % (fn)
		return None

	if file_size != DUMP_SIZE:
		print >>sys.stderr, "%s should be %dk" % (DUMP_SIZE / 1024)
		return None

	return open(fn, 'rb')

def usage():
	print "Usage: %s filename" % (sys.argv[0])

if __name__ == '__main__':
	#read_vmu()
	#sys.exit(0)

	if len(sys.argv) != 2:
		usage()
		sys.exit(1)
	
	vmu_dump = sys.argv[1]
	handle = open_vmu_dump(sys.argv[1])
	if handle is None:
		sys.exit(1)
	
	write_vmu(handle)

	handle.close()

	print "%s written" % (vmu_dump)


