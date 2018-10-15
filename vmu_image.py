"""
Display an image on the VMU.

Image must be a text file containing 32 lines, each 48 characters long. Each
character represents a pixel -- x for black and space for white.
"""
import sys
import argparse

import maple

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', default=maple.PORT)
    parser.add_argument('filename')
    args = parser.parse_args()

    if args.filename == '-':
        image = maple.load_image(sys.stdin)
    else:
        image = maple.load_image(args.filename)

    bus = maple.MapleProxy(args.port)
    bus.deviceInfo(maple.ADDRESS_CONTROLLER)
    bus.deviceInfo(maple.ADDRESS_PERIPH1)
    bus.writeLCD(maple.ADDRESS_PERIPH1, image)

if __name__ == '__main__':
    main()
