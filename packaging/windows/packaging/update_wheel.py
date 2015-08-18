import sys
import argparse
from zipfile import ZipFile, ZIP_DEFLATED
from hashlib import sha256
from wheel.util import urlsafe_b64encode
from collections import namedtuple


def get_sha(data):
    return urlsafe_b64encode(sha256(data).digest())


def modify_wheel(path, name, data):
    with ZipFile(path) as zf:
        zf.getinfo(name)
        new = ZipFile(path + '-new', 'w', ZIP_DEFLATED)
        for item in zf.infolist():
            if item.filename.endswith('dist-info/RECORD'):
                records = zf.read(item.filename)
                newrecord = generate_record(records, name, data)
                new.writestr(item.filename, newrecord)
            elif item.filename == name:
                new.writestr(name, data)
            else:
                zipdata = zf.read(item.filename)
                new.writestr(item.filename, zipdata)


def generate_record(records, name, data):
    data_sha = 'sha256=' + get_sha(data)
    data_size = str(len(data))
    out = []
    Record = namedtuple('Record', 'name hash size')
    for item in records.split():
        record = Record(*item.split(','))
        if record.name != name:
            out.append(item)
        else:
            if not record.hash.startswith('sha256'):
                raise Exception('Unexpected checksum method: {0}'.format(
                    record.hash.split('=')[0]))
            out.append(','.join((record.name, data_sha, data_size)))
    return '\r\n'.join(out)


def parse_args():
    description = """This script will modify wheel file by puting data into
    the target inside wheel archive. It will also update the RECORD file
    with new checksum and file size"""
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument('--path', required=True, help="wheel's file path")
    parser.add_argument('--name', required=True, help='name of the target '
                                                      'file inside wheel')
    parser.add_argument('--data', required=True, help='data to write into '
                                                      'target file')

    return parser.parse_args()


def main():
    args = parse_args()
    if args.data == '-':
        data = sys.stdin.read()
    else:
        data = args.data
    modify_wheel(path=args.path, name=args.name, data=data)


if __name__ == '__main__':
    main()
