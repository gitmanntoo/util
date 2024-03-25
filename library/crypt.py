import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import getpass
import hashlib

def salt_from_seed(phrases: list[str]) -> bytes:
    """Convert a list of seed strings into a sha3 hash as bytes.
    """

    out = b""
    for p in phrases:
        h = hashlib.sha3_256(p.encode())
        out += h.digest() + b"\x00"

    return out


def generate_key(phrases: list[str], length:int = 32) -> bytes:
    """Generate a key from given password and seed strings.
    - phrases is a list of at least two strings
      - the first string is used as the password
      - all other strings are combined to form the salt
    """

    if len(phrases) < 2:
        raise Exception("must provide at least two secret phrases")

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA512(),
        length=length,
        salt=salt_from_seed(phrases[1:]),
        iterations=100000,
        backend=default_backend()
    )
    return base64.urlsafe_b64encode(kdf.derive(phrases[0].encode()))


def encrypt(phrases: list[str], data: bytes) -> bytes:
    # Encrypt data using the given key.
    f = Fernet(generate_key(phrases))
    return f.encrypt(data)


def decrypt(phrases: list[str], data: bytes) -> bytes:
    # Decrypt data using the given key.
    f = Fernet(generate_key(phrases))
    return f.decrypt(data)


def get_multiline_password(prompt: str ="Phrase", terminator: str ='') -> list[str]:
    """
    Collects a multi-line password without displaying the input characters.

    Args:
        prompt (str): Prompt to display to the user.
        terminator (str): The terminator string to indicate end of input. Default is an empty string.

    Returns:
        str: The collected multi-line password.
    """
    lines = []
    while True:
        # Get a line of the password without showing it on the console.
        line = getpass.getpass("{} {}:".format(prompt,len(lines)))
        
        # Check if the terminator was entered, indicating end of input.
        if line == terminator:
            break
        lines.append(line)

    return lines

