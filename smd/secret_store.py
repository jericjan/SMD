"""Basically machine-specific encryption/decryption so that users
don't accidentally share the sensitive information stored in settings.bin"""

import base64
import os

import keyring
from nacl.exceptions import CryptoError
from nacl.secret import SecretBox

SERVICE = "smd_tool"
KEYNAME = "master_key"


def get_secret_box():
    """Reads or generates the master key stored in keyring and then
    returns a SecretBox with that key"""
    b64 = keyring.get_password(SERVICE, KEYNAME)
    if b64:
        return SecretBox(base64.b64decode(b64))
    key = os.urandom(SecretBox.KEY_SIZE)
    keyring.set_password(SERVICE, KEYNAME, base64.b64encode(key).decode())
    return SecretBox(key)


def keyring_encrypt(data: str):
    """Encrypts text"""
    box = get_secret_box()
    blob = box.encrypt(data.encode())  # type: ignore
    return blob


def keyring_decrypt(data: bytes):
    """Returns none if it failed to decrypt (e.g. master key changed)"""
    box = get_secret_box()
    try:
        return box.decrypt(data).decode()
    except CryptoError:
        pass
