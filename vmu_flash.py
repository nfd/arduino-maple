import os
import sys
import time
import struct
import argparse

import maple

WRITE_SIZE = 128
BLOCK_SIZE = 512
DIRECTORY_BLOCK_IDX = 253
DIRECTORY_BLOCK_RANGE = (241, 253)
FAT_BLOCK_IDX = 254
ROOT_BLOCK_IDX = 255

class ImageError(Exception):
    pass

def write_vmu(fs_image, port):
    bus = maple.MapleProxy(port)
    
    # Quick bus enumeration
    bus.deviceInfo(maple.ADDRESS_CONTROLLER)
    bus.deviceInfo(maple.ADDRESS_PERIPH1)
    bus.getMemInfo(maple.ADDRESS_PERIPH1)

    print("Writing %d blocks..." % (len(fs_image)))
    for block_num in sorted(fs_image.keys()):
        print(block_num)
        #orig_data = bus.readFlash(maple.ADDRESS_PERIPH1, block_num, 0)

        target_data = fs_image[block_num]
        assert len(target_data) == BLOCK_SIZE

        for phase_num in range(BLOCK_SIZE // WRITE_SIZE):
            #print block_num, phase_num
            data = target_data[phase_num * WRITE_SIZE : (phase_num + 1) * WRITE_SIZE]
            bus.writeFlash(maple.ADDRESS_PERIPH1, block_num, phase_num, data)

        bus.writeFlashComplete(maple.ADDRESS_PERIPH1, block_num)
    
def read_vmu():
    bus = maple.MapleProxy()

    # Quick bus enumeration
    bus.deviceInfo(maple.ADDRESS_CONTROLLER)
    bus.deviceInfo(maple.ADDRESS_PERIPH1)

    bus.getCond(maple.ADDRESS_CONTROLLER, maple.FN_CONTROLLER)
    bus.getCond(maple.ADDRESS_PERIPH1, maple.FN_CLOCK)
    bus.getMemInfo(maple.ADDRESS_PERIPH1)

    print(bus.readFlash(maple.ADDRESS_PERIPH1, 0, 0))


def pad_to_block_size(data):
    modulus = len(data) % BLOCK_SIZE

    if modulus != 0:
        data += b'\x00' * (BLOCK_SIZE - modulus)

    return data

def read_vmu_dump(fn):
    """
    Return a blocksize-padded image.
    """
    with open(fn, 'rb') as h:
        image_data = h.read()

    return pad_to_block_size(image_data)

def construct_fs_image(filename, data):
    """
    Construct a file system image consisting of a dict mapping block number to block.
    """
    fs_image = {}

    bcd_date = [0x20, 0x18, 0x10, 0x08, 0x23, 0x03, 0x00, 0x00]   # BCD encoded date

    idx = 0
    while idx < len(data):
        fs_image[idx // BLOCK_SIZE] = data[idx : idx + BLOCK_SIZE]
        idx += BLOCK_SIZE

    if DIRECTORY_BLOCK_IDX not in fs_image and FAT_BLOCK_IDX not in fs_image and ROOT_BLOCK_IDX not in fs_image:
        # Construct a directory block
        data_length_blocks = len(data) // BLOCK_SIZE

        filename = os.path.splitext(os.path.basename(filename))[0].upper().replace(' ', '_')
        filename = bytes(filename, encoding='utf-8')
        filename += b'\x00' * (12 - len(filename))

        dir_entry = bytes([
            0xcc,     # file type: game
            0x0,      # no copy protect
            0x0, 0x0  # first block
        ]) + filename + bytes(
            bcd_date + [
            data_length_blocks & 0xff,
            data_length_blocks >> 8,
            0, 1      # header offset within file  --  nb only valid for games
        ])

        fs_image[DIRECTORY_BLOCK_IDX] = pad_to_block_size(dir_entry)

        # construct the FAT block
        fat_list = [0xfffc] * 256  # empty space initially

        # add the game...
        for i in range(len(data) // BLOCK_SIZE):
            fat_list[i] = i + 1
        fat_list[(len(data) // BLOCK_SIZE) - 1] = 0xfffa

        # add the system blocks
        for i in range(DIRECTORY_BLOCK_RANGE[0] + 1, DIRECTORY_BLOCK_RANGE[1] + 1):
            fat_list[i] = i - 1
        fat_list[DIRECTORY_BLOCK_RANGE[0]] = 0xfffa
        fat_list[FAT_BLOCK_IDX] = 0xfffa
        fat_list[ROOT_BLOCK_IDX] = 0xfffa

        fat_bytes = b''.join(struct.pack('<H', entry) for entry in fat_list)
        
        fs_image[FAT_BLOCK_IDX] = fat_bytes

        # contruct the root block
        root_block_list = [
            0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, # magic
            0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, 0x55, # magic
            0x0, 0x0, 0x0, 0x0, 0x0, # standard VMS colour
        ]
        root_block_list += [0 for _ in range(BLOCK_SIZE - len(root_block_list))]
        root_block_list[0x30: 0x38] = bcd_date

        root_block_list[0x46] = FAT_BLOCK_IDX  # fat location, low byte
        root_block_list[0x48] = 1  # fat size, low byte
        root_block_list[0x4a] = DIRECTORY_BLOCK_IDX  # first directory block, low byte
        root_block_list[0x4c] = 13  # directory size in blocks
        root_block_list[0x4e] = 1  # icon shape
        root_block_list[0x50] = 200  # number of user blocks

        root_block = bytes(root_block_list)
        assert len(root_block) == BLOCK_SIZE
        fs_image[ROOT_BLOCK_IDX] = root_block

    return fs_image

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', default=maple.PORT)
    parser.add_argument('image')

    args = parser.parse_args()
    #read_vmu()
    #sys.exit(0)

    vmu_dump = read_vmu_dump(args.image)
    fs_image = construct_fs_image(args.image, vmu_dump)

    write_vmu(fs_image, args.port)

    print("%s written" % (args.image))
