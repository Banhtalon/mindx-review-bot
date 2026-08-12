from dataclasses import replace

import pytest

from mindx_runner.browser_state import (
    ALLOWED_STATE_SITES,
    STORAGE_STATE_DECRYPT_FAILED,
    BrowserStateCipher,
    BrowserStateError,
    BrowserStateLifecycle,
    EncryptedStateEnvelope,
    InMemoryObjectStore,
)

KEY = b"k" * 32
STATE = b'{"synthetic":true}'
WORKSPACE_ID = "11111111-1111-4111-8111-111111111111"


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


def test_wrong_key_version_fails_closed() -> None:
    envelope = BrowserStateCipher(KEY, key_version=1).encrypt(STATE, site="lms")

    with pytest.raises(BrowserStateError) as error:
        BrowserStateCipher(KEY, key_version=2).decrypt(envelope, site="lms")

    assert error.value.code == STORAGE_STATE_DECRYPT_FAILED


def test_tampered_ciphertext_fails_closed() -> None:
    cipher = BrowserStateCipher(KEY, key_version=1)
    envelope = cipher.encrypt(STATE, site="lms")
    tampered_ciphertext = bytes([envelope.ciphertext[0] ^ 1]) + envelope.ciphertext[1:]
    tampered = replace(envelope, ciphertext=tampered_ciphertext)

    with pytest.raises(BrowserStateError) as error:
        cipher.decrypt(tampered, site="lms")

    assert error.value.code == STORAGE_STATE_DECRYPT_FAILED


def test_tampered_gcm_tag_fails_closed() -> None:
    cipher = BrowserStateCipher(KEY, key_version=1)
    envelope = cipher.encrypt(STATE, site="lms")
    tampered_tag = bytes([envelope.tag[0] ^ 1]) + envelope.tag[1:]

    with pytest.raises(BrowserStateError) as error:
        cipher.decrypt(replace(envelope, tag=tampered_tag), site="lms")

    assert error.value.code == STORAGE_STATE_DECRYPT_FAILED


def test_tampered_state_hash_fails_closed() -> None:
    cipher = BrowserStateCipher(KEY, key_version=1)
    envelope = cipher.encrypt(STATE, site="lms")
    tampered_hash = "0" + envelope.state_hash[1:]

    with pytest.raises(BrowserStateError) as error:
        cipher.decrypt(replace(envelope, state_hash=tampered_hash), site="lms")

    assert error.value.code == STORAGE_STATE_DECRYPT_FAILED


def test_malformed_envelope_fails_closed() -> None:
    with pytest.raises(BrowserStateError) as error:
        EncryptedStateEnvelope.from_bytes(b"{\"ciphertext\":\"not-an-envelope\"}")

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


def test_lifecycle_saves_and_loads_state_without_plaintext_in_object() -> None:
    store = InMemoryObjectStore()
    lifecycle = BrowserStateLifecycle(store)
    cipher = BrowserStateCipher(KEY, key_version=1)

    version = lifecycle.persist(WORKSPACE_ID, "lms", STATE, cipher)

    assert version.status == "active"
    assert version.key_version == 1
    assert version.object_path.startswith(f"browser-state/{WORKSPACE_ID}/lms/")
    assert "@" not in version.object_path
    assert STATE not in store.get(version.object_path)
    assert lifecycle.load(WORKSPACE_ID, "lms", cipher) == STATE


def test_saving_new_state_revokes_previous_active_version() -> None:
    store = InMemoryObjectStore()
    lifecycle = BrowserStateLifecycle(store)
    cipher = BrowserStateCipher(KEY, key_version=1)

    previous = lifecycle.persist(WORKSPACE_ID, "teaching", STATE, cipher)
    current = lifecycle.persist(WORKSPACE_ID, "teaching", b'{"synthetic":2}', cipher)

    assert lifecycle.get_version(previous.version_id).status == "revoked"
    assert lifecycle.get_version(current.version_id).status == "active"
    assert lifecycle.load(WORKSPACE_ID, "teaching", cipher) == b'{"synthetic":2}'


def test_key_rotation_activates_a_new_key_version() -> None:
    store = InMemoryObjectStore()
    lifecycle = BrowserStateLifecycle(store)

    lifecycle.persist(WORKSPACE_ID, "lms", STATE, BrowserStateCipher(KEY, key_version=1))
    rotated = lifecycle.persist(
        WORKSPACE_ID,
        "lms",
        STATE,
        BrowserStateCipher(b"r" * 32, key_version=2),
    )

    assert rotated.key_version == 2
    assert lifecycle.load(
        WORKSPACE_ID,
        "lms",
        BrowserStateCipher(b"r" * 32, key_version=2),
    ) == STATE


def test_reset_revokes_version_deletes_object_and_forces_fresh_login() -> None:
    store = InMemoryObjectStore()
    lifecycle = BrowserStateLifecycle(store)
    cipher = BrowserStateCipher(KEY, key_version=1)
    version = lifecycle.persist(WORKSPACE_ID, "lms", STATE, cipher)

    lifecycle.reset(WORKSPACE_ID, "lms")

    assert lifecycle.get_version(version.version_id).status == "revoked"
    assert version.object_path not in store.paths
    with pytest.raises(BrowserStateError) as error:
        lifecycle.load(WORKSPACE_ID, "lms", cipher)
    assert error.value.code == STORAGE_STATE_DECRYPT_FAILED


def test_tampered_stored_envelope_fails_closed() -> None:
    store = InMemoryObjectStore()
    lifecycle = BrowserStateLifecycle(store)
    cipher = BrowserStateCipher(KEY, key_version=1)
    version = lifecycle.persist(WORKSPACE_ID, "lms", STATE, cipher)
    stored = bytearray(store.get(version.object_path))
    stored[-2] = ord("0") if stored[-2] != ord("0") else ord("1")
    store.put(version.object_path, bytes(stored))

    with pytest.raises(BrowserStateError) as error:
        lifecycle.load(WORKSPACE_ID, "lms", cipher)

    assert error.value.code == STORAGE_STATE_DECRYPT_FAILED


def test_lifecycle_rejects_unknown_sites_and_non_uuid_workspaces() -> None:
    store = InMemoryObjectStore()
    lifecycle = BrowserStateLifecycle(store)
    cipher = BrowserStateCipher(KEY, key_version=1)

    assert ALLOWED_STATE_SITES == frozenset({"teaching", "lms"})
    with pytest.raises(BrowserStateError):
        lifecycle.persist("not-a-uuid", "lms", STATE, cipher)
    with pytest.raises(BrowserStateError):
        lifecycle.persist(WORKSPACE_ID, "unknown", STATE, cipher)
