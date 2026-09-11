# Copyright (c) 2025 MX
# Adapted from mxyooR/Kuro_login (MIT). See docs/licenses/Kuro_login.txt.
import json
import random
import string
import time
from typing import Any

from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Util.Padding import pad

from .consts import RSA_KEY_E, RSA_KEY_N


def random_string(alphabet: str, length: int) -> str:
    random_string_list = [random.choice(alphabet) for i in range(length)]
    return "".join(random_string_list)


def get_current_timestamp(is_ms: bool = True):
    current_time = time.time()
    if is_ms:
        current_time = current_time * 1000
    return round(current_time)


def get_guid():
    alphabet = string.ascii_lowercase + string.digits
    return random_string(alphabet=alphabet, length=16)


def geetest_rsa_enc(plaintext: str) -> str:
    public_key = RSA.construct((RSA_KEY_N, RSA_KEY_E))
    padding_public_key = PKCS1_v1_5.new(public_key)
    cipher_bytes = padding_public_key.encrypt(plaintext.encode("utf-8"))
    cipher_hex = cipher_bytes.hex()
    if len(cipher_hex) % 2 != 0:
        cipher_hex = "0" + cipher_hex
    return cipher_hex


def geetest_m(track: dict[str, Any]):
    key = get_guid()
    rsa_enc = geetest_rsa_enc(plaintext=key)

    iv = "0000000000000000".encode("utf-8")
    plaintext = json.dumps(track).encode("utf-8")
    padding_plaintext = pad(plaintext, 16, "pkcs7")
    aes = AES.new(key=key.encode("utf-8"), mode=AES.MODE_CBC, iv=iv)
    aes_enc = aes.encrypt(padding_plaintext).hex()
    return aes_enc + rsa_enc
