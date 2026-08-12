from dataclasses import replace

import pytest

from mindx_runner.browser_state import (
    STORAGE_STATE_DECRYPT_FAILED,
    BrowserStateCipher,
    BrowserStateError,
    EncryptedStateEnvelope,
)

KEY = b"k" * 32
STATE = b'{"synthetic":true}'


def test_encrypt_decrypt_round_trip_serializes_only_the_envelope() -> None:
    cipher = BrowserStateCipher(KEY, key_version=7)

    envelope = cipher.encrypt(STATE, site="lms")
    serialized = envelope.to_bytes()
    decoded = EncryptedStateEnvelope.from_bytes(serialized)

    assert cipher.decrypt(decoded, site="lms") == STATE
    assert decoded.key_version == 7
    assert STATE not in serialized


def test_each_encryption_uses_a_fresh_nonce() -> None:
    cipher = BrowserStateCipher(KEY, key_version=1)

    first = cipher.encrypt(STATE, site="teaching")
    second = cipher.encrypt(STATE, site="teaching")

    assert first.iv != second.iv


def test_wrong_key_fails_closed_without_exposing_plaintext() -> None:
    envelope = BrowserStateCipher(KEY, key_version=1).encrypt(STATE, site="lms")

    with pytest.raises(BrowserStateError) as error:
        BrowserStateCipher(b"x" * 32, key_version=1).decrypt(envelope, site="lms")

    assert error.value.code == STORAGE_STATE_DECRYPT_FAILED
    assert str(error.value) == STORAGE_STATE_DECRYPT_FAILED


def test_tampered_ciphertext_fails_closed() -> None:
    cipher = BrowserStateCipher(KEY, key_version=1)
    envelope = cipher.encrypt(STATE, site="lms")
    tampered_ciphertext = bytes([envelope.ciphertext[0] ^ 1]) + envelope.ciphertext[1:]
    tampered = replace(envelope, ciphertext=tampered_ciphertext)

    with pytest.raises(BrowserStateError) as error:
        cipher.decrypt(tampered, site="lms")

    assert error.value.code == STORAGE_STATE_DECRYPT_FAILED


def test_state_is_bound_to_its_site() -> None:
    cipher = BrowserStateCipher(KEY, key_version=1)
    envelope = cipher.encrypt(STATE, site="teaching")

    with pytest.raises(BrowserStateError) as error:
        cipher.decrypt(envelope, site="lms")

    assert error.value.code == STORAGE_STATE_DECRYPT_FAILED


def test_key_must_be_exactly_32_bytes() -> None:
    with pytest.raises(BrowserStateError) as error:
        BrowserStateCipher(b"short", key_version=1)

    assert error.value.code == STORAGE_STATE_DECRYPT_FAILED
