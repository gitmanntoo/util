#!/usr/bin/python3

import argparse
import base64
from library import crypt
import sys


def read_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Encrypt a message using a key derived from two phrases.",
    )
    parser.add_argument("-d", "--decrypt",
        dest="decrypt",
        action="store_true",
        required=False,
        help="Optionally decrypt instead of encrypt."
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

    if args.input is not None:
        with open(args.input, "rb") as fh:
            msg_bytes = fh.read()
    else:
        if args.decrypt:
            print("Message (base64): ")
            lines = []
            for line in sys.stdin:
                if line == "":
                    break
                lines.append(line)
            msg = "".join(lines)
            msg_bytes = base64.b64decode(msg.encode())
        else:
            print("Message:")
            lines = []
            for line in sys.stdin:
                if line == "":
                    break
                lines.append(line)
            msg = "".join(lines)
            msg_bytes = msg.encode()

    if args.decrypt:
        out = crypt.decrypt(phrases, msg_bytes)
    else:
        out = crypt.encrypt(phrases, msg_bytes)

    if args.output is not None:
        with open(args.output, "wb") as fh:
            fh.write(out)
    else:
        if args.decrypt:
            print(out.decode())
        else:
            print(base64.b64encode(out).decode())


if __name__ == "__main__":
    main()