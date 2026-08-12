# Encrypted Browser State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a synthetic, fail-closed AES-256-GCM browser-state encryption and save/load/reset lifecycle to the Python runner.

**Architecture:** A pure `BrowserStateCipher` owns envelope validation, AES-GCM encryption/decryption and site-bound AAD. A `BrowserStateLifecycle` owns version metadata and talks to a small object-store protocol, allowing deterministic in-memory tests without real Supabase Storage or credentials.

**Tech Stack:** Python 3.12, `cryptography` AESGCM, pytest, Ruff, mypy, existing `mindx_runner` package.

## Global Constraints

- Browser state được mã hóa AES-256-GCM trước khi upload.
- Mỗi object có `key_version`, `iv`, `tag`, `ciphertext`.
- Key mã hóa không nằm trong Supabase Storage/Postgres.
- Object path không chứa username/email.
- Reset state phải xóa version hiện tại và buộc login mới.
- Không ghi credential, cookie, token hoặc PII vào log/evidence.
- MVP 1 chỉ đọc Teaching và LMS; không có LMS Save/Submit.
- Test data is synthetic only.

---

### Task 1: Add the crypto dependency and failing crypto tests

**Files:**
- Modify: `apps/browser-runner/pyproject.toml`
- Modify: `apps/browser-runner/uv.lock` via `uv lock`
- Create: `apps/browser-runner/tests/unit/test_browser_state.py`

**Interfaces:**
- The tests will import `BrowserStateCipher`, `BrowserStateError` and
  `STORAGE_STATE_DECRYPT_FAILED` from `mindx_runner.browser_state`.

- [ ] **Step 1: Add tests for the missing crypto API**

  Cover round-trip, fresh nonce, wrong key, tampered ciphertext, site binding,
  key version and invalid key length. Use only `b'{"synthetic":true}'`.

- [ ] **Step 2: Run the focused test to verify RED**

  Run:

  ```powershell
  uv run --project apps/browser-runner pytest apps/browser-runner/tests/unit/test_browser_state.py -q
  ```

  Expected: collection fails because `mindx_runner.browser_state` does not yet
  exist.

- [ ] **Step 3: Add the direct `cryptography` dependency**

  Add `cryptography>=50,<51` to the project dependencies and run:

  ```powershell
  uv lock --project apps/browser-runner
  ```

- [ ] **Step 4: Commit the dependency and test contract**

  ```powershell
  git add apps/browser-runner/pyproject.toml apps/browser-runner/uv.lock apps/browser-runner/tests/unit/test_browser_state.py
  git commit -m "test: define encrypted browser state contract"
  ```

### Task 2: Implement AES-GCM envelope crypto

**Files:**
- Create: `apps/browser-runner/src/mindx_runner/browser_state.py`
- Test: `apps/browser-runner/tests/unit/test_browser_state.py`

**Interfaces:**
- `BrowserStateCipher(key: bytes, key_version: int)`
- `BrowserStateCipher.encrypt(state: bytes, site: str) -> EncryptedStateEnvelope`
- `BrowserStateCipher.decrypt(envelope: EncryptedStateEnvelope, site: str) -> bytes`
- `EncryptedStateEnvelope.to_bytes() -> bytes`
- `EncryptedStateEnvelope.from_bytes(value: bytes) -> EncryptedStateEnvelope`
- `BrowserStateError.code: str`

- [ ] **Step 1: Implement strict site/key/envelope validation and AES-GCM**

  Use a 32-byte key, 12-byte random nonce, site-bound AAD, split the GCM tag
  from the ciphertext, base64 encode envelope binary fields, and verify the
  SHA-256 plaintext hash after decryption.

- [ ] **Step 2: Run focused tests to verify GREEN**

  ```powershell
  uv run --project apps/browser-runner pytest apps/browser-runner/tests/unit/test_browser_state.py -q
  ```

  Expected: all crypto tests pass and no plaintext state is included in the
  serialized envelope.

- [ ] **Step 3: Run Ruff and mypy for the changed module**

  ```powershell
  uv run --project apps/browser-runner ruff check apps/browser-runner/src/mindx_runner/browser_state.py apps/browser-runner/tests/unit/test_browser_state.py
  uv run --project apps/browser-runner mypy apps/browser-runner/src
  ```

### Task 3: Add synthetic save/load/reset lifecycle

**Files:**
- Modify: `apps/browser-runner/src/mindx_runner/browser_state.py`
- Modify: `apps/browser-runner/tests/unit/test_browser_state.py`

**Interfaces:**
- `ObjectStore` protocol with `put(path, value)`, `get(path)`, and `delete(path)`.
- `InMemoryObjectStore` for synthetic tests.
- `BrowserStateLifecycle.persist(workspace_id, site, state, cipher) -> BrowserStateVersion`
- `BrowserStateLifecycle.load(workspace_id, site, cipher) -> bytes`
- `BrowserStateLifecycle.reset(workspace_id, site) -> None`
- `BrowserStateVersion.status` values `active` and `revoked`.

- [ ] **Step 1: Write lifecycle tests**

  Cover path safety, replacing an active version, loading the active state,
  reset deletion, missing-state failure and cleanup after failed reads.

- [ ] **Step 2: Run lifecycle tests to verify RED**

  ```powershell
  uv run --project apps/browser-runner pytest apps/browser-runner/tests/unit/test_browser_state.py -q
  ```

  Expected: lifecycle imports or assertions fail before implementation.

- [ ] **Step 3: Implement the protocol-backed lifecycle**

  Store only envelopes, keep metadata in memory for this synthetic boundary,
  revoke old versions before activating the new one, and delete the object on
  reset. Reject non-UUID workspace IDs and any path segment outside the
  `teaching`/`lms` allowlist.

- [ ] **Step 4: Run all browser-runner tests**

  ```powershell
  uv run --project apps/browser-runner pytest
  ```

  Expected: all tests pass with no real browser state created.

### Task 4: Record evidence and verify the repository

**Files:**
- Modify: `docs/evidence/spike-0/V4-S0-09.md`
- Modify: `docs/evidence/index.json`
- Modify: `docs/evidence/spike-0/metrics.csv`
- Modify: `docs/phase-reports/spike-0.md`

**Interfaces:**
- Evidence records synthetic crypto/lifecycle results only. It does not mark
  live Teaching/LMS probes or production Storage as complete.

- [ ] **Step 1: Update the evidence record with synthetic results**

  Record round-trip, tamper/wrong-key rejection, rotation and reset cleanup;
  explicitly state that no real browser state or secret was created.

- [ ] **Step 2: Run all required verification commands**

  ```powershell
  uv run --project apps/browser-runner ruff check .
  uv run --project apps/browser-runner mypy src
  uv run --project apps/browser-runner pytest
  npm run lint
  npm run typecheck
  npm run test
  npm run build
  npm run verify:no-secrets
  npm run verify:no-live-write
  npm run test:rls
  ```

- [ ] **Step 3: Review the diff and commit**

  ```powershell
  git diff --check
  git status --short
  git add apps/browser-runner docs/evidence docs/phase-reports/spike-0.md
  git commit -m "feat: add encrypted browser state lifecycle"
  ```
