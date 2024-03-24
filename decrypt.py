#!/usr/bin/python3

import argparse
import base64
from lib import crypt


def read_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Decrypt a message or file using a key derived from two phrases.",
    )
    parser.add_argument("-f", "--file",
        dest="input",
        help="Optional file to encrypt. File input is read as bytes."
    )
    parser.add_argument("-o","--output",
        dest="output",
        help="Optional output file. If specified, output is written as bytes."
    )

    return parser.parse_args()


def main():
    args = read_args()

    phrases = crypt.get_multiline_password()

    if args.input is None:
        msg = input("Message as base64: ")
        msg_bytes = base64.b64decode(msg.encode())
    else:
        with open(args.input, "rb") as fh:
            msg_bytes = fh.read()

    d = crypt.decrypt(phrases, msg_bytes)

    if args.output is not None:
        with open(args.output, "wb") as fh:
            fh.write(d)
    else:
        print(d.decode())


if __name__ == "__main__":
    main()