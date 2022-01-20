
"""Wrapper functions to encapsulate libsodium and API details."""

import base64
import json

import libnacl
import libnacl.sealed
import libnacl.public
import libnacl.utils
import requests

from tsdapiclient.exc import AuthzError
from tsdapiclient.tools import HOSTS, debug_step, handle_request_errors


def nacl_encrypt_data(data: bytes, nonce: bytes, key: bytes) -> bytes:
    return libnacl.crypto_stream_xor(data, nonce, key)


def nacl_decrypt_data(data: bytes, nonce: bytes, key: bytes) -> bytes:
    return libnacl.crypto_stream_xor(data, nonce, key)


def nacl_gen_nonce() -> bytes:
    return libnacl.utils.rand_nonce()


def nacl_gen_key() -> bytes:
    return libnacl.utils.salsa_key()


@handle_request_errors
def nacl_get_server_public_key(env: str, pnum: str, token: str) -> bytes:
    host = HOSTS.get(env)
    debug_step('getting public key')
    resp = requests.get(
        f'https://{host}/v1/{pnum}/files/crypto/key',
        headers={'Authorization': f'Bearer {token}'},
    )
    if resp.status_code != 200:
        raise AuthzError
    encoded_public_key = json.loads(resp.text).get('public_key')
    return libnacl.public.PublicKey(base64.b64decode(encoded_public_key))


def nacl_encrypt_header(public_key: bytes, header: bytes) -> bytes:
    sbox = libnacl.sealed.SealedBox(public_key)
    return sbox.encrypt(header)


def nacl_encode_header(header: bytes) -> str:
    return base64.b64encode(header)
