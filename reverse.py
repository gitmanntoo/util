#!/usr/bin/python3

import argparse
import sys


def read_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reverse strings and lines.",
    )
    parser.add_argument("-l","--lines",
        dest="lines",
        action="store_true",
        required=False,
        help="Optionally reverse line order from input.",
    )
    parser.add_argument("-f","--file",
        dest="input",
        required=False,
        help="Optional input file to reverse.",
    )

    return parser.parse_args()


def main():
    args = read_args()

    # Read lines from stdin or file.
    lines = []
    if args.input is None:
        for line in sys.stdin:
            lines.append(line.rstrip("\r\n"))
    else:
       with open(args.input, "r") as fh:
           for line in fh:
            lines.append(line.rstrip("\r\n"))

    # Reverse each line.
    for i in range(len(lines)):
        lines[i] = lines[i][::-1]

    # Print output lines
    if args.lines:
        print("\n".join(lines[::-1]))
    else:
        print("\n".join(lines))


if __name__ == "__main__":
    main()