import base64
import os

import keyring
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
    box = get_secret_box()
    blob = box.encrypt(data.encode())  # type: ignore
    return blob


def keyring_decrypt(data: bytes):
    box = get_secret_box()
    return box.decrypt(data).decode()
