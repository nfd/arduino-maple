import os
import sys
import maple
import argparse

LAST_BLOCK = 255

def read_vmu(port, start_block=0, end_block=LAST_BLOCK):
    bus = maple.MapleProxy(port)

    # Quick bus enumeration
    bus.deviceInfo(maple.ADDRESS_CONTROLLER)
    bus.deviceInfo(maple.ADDRESS_PERIPH1)

    bus.getCond(maple.ADDRESS_CONTROLLER, maple.FN_CONTROLLER)
    bus.getCond(maple.ADDRESS_PERIPH1, maple.FN_CLOCK)
    bus.getMemInfo(maple.ADDRESS_PERIPH1)

    for block_num in range(start_block, end_block + 1):
        sys.stdout.write(chr(13) + chr(27) + '[K' + 'Reading block %d of 255' % (block_num,))
        sys.stdout.flush()
        data = bus.readFlash(maple.ADDRESS_PERIPH1, block_num, 0)
        yield data

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', default=maple.PORT)
    parser.add_argument('filename')
    args = parser.parse_args()

    open_mode = 'wb'
    start_block = 0

    if os.path.exists(args.filename):
        size = os.stat(args.filename).st_size
        if size % 512 == 0:
            print('Extending previous file')
            open_mode = 'ab'
            start_block = size // 512

    with open(args.filename, open_mode) as handle:
        for block in read_vmu(args.port, start_block=start_block):
            handle.write(block)
            handle.flush()

if __name__ == '__main__':
    main()

