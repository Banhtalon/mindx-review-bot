import base64
import hashlib
import hmac
import json
import os
from dataclasses import dataclass, replace
from typing import Final, Literal, NoReturn, Protocol
from uuid import UUID, uuid4

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

STORAGE_STATE_DECRYPT_FAILED: Final[str] = "STORAGE_STATE_DECRYPT_FAILED"
ALLOWED_STATE_SITES: Final[frozenset[str]] = frozenset({"teaching", "lms"})
AES256_KEY_BYTES: Final[int] = 32
GCM_NONCE_BYTES: Final[int] = 12
GCM_TAG_BYTES: Final[int] = 16
ENVELOPE_SCHEMA_VERSION: Final[int] = 1


class BrowserStateError(RuntimeError):
    def __init__(self, code: str = STORAGE_STATE_DECRYPT_FAILED) -> None:
        self.code = code
        super().__init__(code)


def _fail() -> NoReturn:
    raise BrowserStateError()


def _validate_site(site: str) -> None:
    if site not in ALLOWED_STATE_SITES:
        _fail()


def _validate_key_version(key_version: int) -> None:
    if isinstance(key_version, bool) or key_version < 1:
        _fail()


def _associated_data(site: str, key_version: int) -> bytes:
    _validate_site(site)
    _validate_key_version(key_version)
    return f"mindx-browser-state:v{ENVELOPE_SCHEMA_VERSION}:{site}:key-{key_version}".encode(
        "ascii"
    )


def _encode_binary(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii")


def _decode_binary(value: object) -> bytes:
    if not isinstance(value, str):
        _fail()
    try:
        return base64.b64decode(value.encode("ascii"), altchars=b"-_", validate=True)
    except (UnicodeEncodeError, ValueError):
        _fail()


@dataclass(frozen=True, slots=True)
class EncryptedStateEnvelope:
    key_version: int
    iv: bytes
    tag: bytes
    ciphertext: bytes
    state_hash: str

    def to_bytes(self) -> bytes:
        _validate_key_version(self.key_version)
        if len(self.iv) != GCM_NONCE_BYTES or len(self.tag) != GCM_TAG_BYTES:
            _fail()
        if len(self.state_hash) != hashlib.sha256().digest_size * 2:
            _fail()
        payload = {
            "ciphertext": _encode_binary(self.ciphertext),
            "iv": _encode_binary(self.iv),
            "key_version": self.key_version,
            "schema_version": ENVELOPE_SCHEMA_VERSION,
            "state_hash": self.state_hash,
            "tag": _encode_binary(self.tag),
        }
        return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("ascii")

    @classmethod
    def from_bytes(cls, value: bytes) -> "EncryptedStateEnvelope":
        if not isinstance(value, bytes):
            _fail()
        try:
            payload = json.loads(value.decode("ascii"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            _fail()
        if not isinstance(payload, dict):
            _fail()
        expected_keys = {"ciphertext", "iv", "key_version", "schema_version", "state_hash", "tag"}
        if set(payload) != expected_keys:
            _fail()
        key_version = payload["key_version"]
        if not isinstance(key_version, int) or isinstance(key_version, bool):
            _fail()
        _validate_key_version(key_version)
        if payload["schema_version"] != ENVELOPE_SCHEMA_VERSION:
            _fail()
        state_hash = payload["state_hash"]
        if (
            not isinstance(state_hash, str)
            or len(state_hash) != hashlib.sha256().digest_size * 2
            or any(character not in "0123456789abcdef" for character in state_hash.lower())
        ):
            _fail()
        iv = _decode_binary(payload["iv"])
        tag = _decode_binary(payload["tag"])
        ciphertext = _decode_binary(payload["ciphertext"])
        if len(iv) != GCM_NONCE_BYTES or len(tag) != GCM_TAG_BYTES:
            _fail()
        return cls(
            key_version=key_version,
            iv=iv,
            tag=tag,
            ciphertext=ciphertext,
            state_hash=state_hash,
        )


class BrowserStateCipher:
    def __init__(self, key: bytes, key_version: int) -> None:
        if not isinstance(key, bytes) or len(key) != AES256_KEY_BYTES:
            _fail()
        _validate_key_version(key_version)
        self._key = key
        self.key_version = key_version

    def encrypt(self, state: bytes, *, site: str) -> EncryptedStateEnvelope:
        if not isinstance(state, bytes):
            _fail()
        iv = os.urandom(GCM_NONCE_BYTES)
        encrypted = AESGCM(self._key).encrypt(
            iv,
            state,
            _associated_data(site, self.key_version),
        )
        return EncryptedStateEnvelope(
            key_version=self.key_version,
            iv=iv,
            tag=encrypted[-GCM_TAG_BYTES:],
            ciphertext=encrypted[:-GCM_TAG_BYTES],
            state_hash=hashlib.sha256(state).hexdigest(),
        )

    def decrypt(self, envelope: EncryptedStateEnvelope, *, site: str) -> bytes:
        if not isinstance(envelope, EncryptedStateEnvelope):
            _fail()
        try:
            plaintext = AESGCM(self._key).decrypt(
                envelope.iv,
                envelope.ciphertext + envelope.tag,
                _associated_data(site, envelope.key_version),
            )
        except (InvalidTag, ValueError, TypeError):
            _fail()
        if not hmac.compare_digest(hashlib.sha256(plaintext).hexdigest(), envelope.state_hash):
            _fail()
        return plaintext


BrowserStateStatus = Literal["active", "revoked"]


class ObjectStore(Protocol):
    def put(self, path: str, value: bytes) -> None:
        ...

    def get(self, path: str) -> bytes:
        ...

    def delete(self, path: str) -> None:
        ...


class InMemoryObjectStore:
    def __init__(self) -> None:
        self._objects: dict[str, bytes] = {}

    @property
    def paths(self) -> frozenset[str]:
        return frozenset(self._objects)

    def put(self, path: str, value: bytes) -> None:
        self._objects[path] = bytes(value)

    def get(self, path: str) -> bytes:
        return self._objects[path]

    def delete(self, path: str) -> None:
        del self._objects[path]


@dataclass(frozen=True, slots=True)
class BrowserStateVersion:
    version_id: str
    workspace_id: str
    site: str
    object_path: str
    key_version: int
    state_hash: str
    status: BrowserStateStatus


def _canonical_workspace_id(workspace_id: str) -> str:
    try:
        return str(UUID(workspace_id))
    except (AttributeError, TypeError, ValueError):
        _fail()


class BrowserStateLifecycle:
    def __init__(self, store: ObjectStore) -> None:
        self._store = store
        self._versions: dict[tuple[str, str], list[BrowserStateVersion]] = {}

    def persist(
        self,
        workspace_id: str,
        site: str,
        state: bytes,
        cipher: BrowserStateCipher,
    ) -> BrowserStateVersion:
        canonical_workspace_id = _canonical_workspace_id(workspace_id)
        _validate_site(site)
        envelope = cipher.encrypt(state, site=site)
        version_id = str(uuid4())
        object_path = f"browser-state/{canonical_workspace_id}/{site}/{version_id}.json"
        self._store.put(object_path, envelope.to_bytes())

        key = (canonical_workspace_id, site)
        previous_versions = self._versions.get(key, [])
        revoked_versions = [
            version if version.status == "revoked" else replace(version, status="revoked")
            for version in previous_versions
        ]
        current = BrowserStateVersion(
            version_id=version_id,
            workspace_id=canonical_workspace_id,
            site=site,
            object_path=object_path,
            key_version=envelope.key_version,
            state_hash=envelope.state_hash,
            status="active",
        )
        self._versions[key] = [*revoked_versions, current]
        return current

    def load(
        self,
        workspace_id: str,
        site: str,
        cipher: BrowserStateCipher,
    ) -> bytes:
        active = self._active_version(workspace_id, site)
        if active is None:
            _fail()
        try:
            envelope = EncryptedStateEnvelope.from_bytes(self._store.get(active.object_path))
        except (BrowserStateError, KeyError, OSError):
            _fail()
        return cipher.decrypt(envelope, site=site)

    def reset(self, workspace_id: str, site: str) -> None:
        active = self._active_version(workspace_id, site)
        if active is None:
            return
        try:
            self._store.delete(active.object_path)
        except (KeyError, OSError):
            pass
        self._replace_version(active, status="revoked")

    def get_version(self, version_id: str) -> BrowserStateVersion:
        for versions in self._versions.values():
            for version in versions:
                if version.version_id == version_id:
                    return version
        _fail()

    def _active_version(self, workspace_id: str, site: str) -> BrowserStateVersion | None:
        canonical_workspace_id = _canonical_workspace_id(workspace_id)
        _validate_site(site)
        versions = self._versions.get((canonical_workspace_id, site), [])
        return next((version for version in versions if version.status == "active"), None)

    def _replace_version(self, version: BrowserStateVersion, *, status: BrowserStateStatus) -> None:
        key = (version.workspace_id, version.site)
        self._versions[key] = [
            replace(candidate, status=status)
            if candidate.version_id == version.version_id
            else candidate
            for candidate in self._versions.get(key, [])
        ]
