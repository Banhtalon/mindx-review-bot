# Encrypted Browser State Design

**Date:** 2026-08-12
**Scope:** Spike 0 synthetic encrypted browser-state lifecycle

## Goal

Provide a small, testable browser-state crypto and lifecycle boundary before
any real Teaching/LMS credentials or browser state are used.

## Decisions

- Use Python `cryptography` with AES-256-GCM.
- Require a 32-byte encryption key and generate a fresh 12-byte nonce for every
  encryption operation.
- Store an opaque JSON envelope containing `key_version`, `iv`, `tag`,
  `ciphertext`, and a SHA-256 `state_hash`. The plaintext state is never part
  of logs or metadata.
- Bind ciphertext to the target site through authenticated additional data so a
  Teaching state cannot be replayed as an LMS state.
- Keep key material outside Storage/Postgres. The runner receives it only from
  its environment at runtime.
- Use a storage protocol and in-memory implementation for the synthetic
  lifecycle. A Supabase Storage adapter and live browser login are outside this
  change and require owner-entered secrets later.
- Saving a new version revokes the previous active version. Reset revokes and
  deletes the active object, forcing a fresh login on the next run.
- Convert cryptographic, malformed-envelope, missing-object and hash failures
  into the safe `STORAGE_STATE_DECRYPT_FAILED` boundary; never expose raw
  exception text or plaintext state.

## Data flow

```text
state bytes + runtime key
    -> AES-256-GCM encrypt(site AAD)
    -> JSON envelope + state hash
    -> object store path: browser-state/{workspace_uuid}/{site}/...

object envelope + runtime key
    -> validate envelope and site AAD
    -> AES-256-GCM decrypt
    -> verify state hash
    -> temporary browser state bytes
```

The object path contains only a UUID, an allowlisted site and an opaque hash;
it never contains a username, email, credential or cookie value.

## Error and security boundaries

- Key length other than 32 bytes is rejected before encryption/decryption.
- `teaching` and `lms` are the only accepted sites.
- Envelope fields are strictly typed and base64 decoded before decryption.
- Wrong key, wrong site, tampered ciphertext and state-hash mismatch fail
  closed.
- Tests use synthetic JSON only. No real cookie, token, credential, URL or
  student data is created.

## Verification

- Unit tests cover round-trip encryption, fresh nonces, wrong-key rejection,
  tamper rejection, key-version metadata, site binding, rotation, reset and
  object cleanup.
- Ruff, mypy and pytest run for the browser runner.
- The evidence record remains synthetic; live Teaching/LMS and production
  Storage deployment remain separate gates.
