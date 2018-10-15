import sys

def read_pgm(filename):
    if hasattr(filename, 'readline'):
        handle = filename
        closeme = False
    else:
        handle= open(filename, 'rb')
        closeme = True

    format = handle.readline().decode('ascii')
    dims = handle.readline().decode('ascii')
    levels = handle.readline().decode('ascii')
    data = handle.readline()

    if closeme:
        handle.close()

    return format, dims, levels, data

def main(pathname):
    if pathname == '-':
        pathname = sys.stdin.buffer

    format, dims, levels, data = read_pgm(pathname)

    dims = dims.split(' ', 1)
    width, height = int(dims[0]), int(dims[1])

    levels = int(levels)

    if levels > 255:
        raise NotImplementedError()

    threshold = levels // 2

    for idx, b in enumerate(data):
        sys.stdout.write('x' if b < threshold else ' ')
        if idx % width == width - 1:
            sys.stdout.write('\n')

if __name__ == '__main__':
    main(sys.argv[1])
