from lib import crypt
import string

def test_encrypt_decrypt():
    # Verify that encrypt/decrypt returns the input message.
    phrase1 = string.punctuation
    phrase2 = string.ascii_uppercase
    message = string.ascii_letters + "Hello, World!" + string.punctuation

    
    e = crypt
