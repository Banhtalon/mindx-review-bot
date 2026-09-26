import type {
  CommitDraftResult,
  SyntheticReviewDraftSnapshot,
  SyntheticReviewDraftStore,
  SyntheticReviewInput,
} from "./contracts";
import { REVIEW_NOTE_MAX_LENGTH } from "./contracts";

/** The persisted shape is versioned so an old browser value cannot silently
 * become a newer draft after the input contract changes. */
export const REVIEW_DRAFT_STORAGE_VERSION = 1 as const;
export const REVIEW_DRAFT_STORAGE_PREFIX = "mindx-review-draft:v1:";

export type ReviewDraftStorage = Pick<Storage, "getItem" | "setItem">;

type PersistedReviewDraft = {
  readonly schemaVersion: typeof REVIEW_DRAFT_STORAGE_VERSION;
  readonly sessionKey: string;
  readonly revision: number;
  readonly inputs: readonly SyntheticReviewInput[];
};

export type DraftStoreOptions = {
  /** Pass a storage implementation in tests or for an embedded host. */
  readonly storage?: ReviewDraftStorage | null;
  readonly storageKey?: string;
};

export type DraftPersistenceStatus = "persistent" | "memory";

const ATTENDANCE_VALUES = new Set<SyntheticReviewInput["attendance"]>([
  "present",
  "absent",
  "unknown",
]);
const LEVEL_VALUES = new Set<SyntheticReviewInput["level"]>([
  "strong",
  "developing",
  "needs_support",
  "unknown",
]);

function freezeInputs(
  inputs: readonly SyntheticReviewInput[],
): readonly SyntheticReviewInput[] {
  return Object.freeze(inputs.map((input) => Object.freeze({ ...input })));
}

function freezeSnapshot(
  sessionKey: string,
  revision: number,
  inputs: readonly SyntheticReviewInput[],
): SyntheticReviewDraftSnapshot {
  return Object.freeze({
    sessionKey,
    revision,
    inputs: freezeInputs(inputs),
  });
}

function getDefaultStorage(): ReviewDraftStorage | null {
  try {
    if (typeof window === "undefined") return null;
    return window.localStorage;
  } catch {
    // Browsers may deny localStorage for private or restricted documents.
    return null;
  }
}

function hasUniqueStableKeys(inputs: readonly SyntheticReviewInput[]): boolean {
  const keys = inputs.map((input) => input.rowKey);
  return keys.every((key) => typeof key === "string" && key.trim().length > 0) &&
    new Set(keys).size === keys.length;
}

function isReviewInput(value: unknown): value is SyntheticReviewInput {
  if (typeof value !== "object" || value === null) return false;

  const input = value as Partial<SyntheticReviewInput>;
  return (
    typeof input.rowKey === "string" &&
    input.rowKey.trim().length > 0 &&
    typeof input.noteDraft === "string" &&
    input.noteDraft.length <= REVIEW_NOTE_MAX_LENGTH &&
    typeof input.attendance === "string" &&
    ATTENDANCE_VALUES.has(input.attendance as SyntheticReviewInput["attendance"]) &&
    typeof input.level === "string" &&
    LEVEL_VALUES.has(input.level as SyntheticReviewInput["level"])
  );
}

function isPersistedDraft(
  value: unknown,
  sessionKey: string,
  initialInputs: readonly SyntheticReviewInput[],
): value is PersistedReviewDraft {
  if (typeof value !== "object" || value === null) return false;

  const draft = value as Partial<PersistedReviewDraft>;
  const revision = draft.revision;
  if (
    draft.schemaVersion !== REVIEW_DRAFT_STORAGE_VERSION ||
    draft.sessionKey !== sessionKey ||
    typeof revision !== "number" ||
    !Number.isSafeInteger(revision) ||
    revision < 1 ||
    !Array.isArray(draft.inputs) ||
    !draft.inputs.every(isReviewInput) ||
    !hasUniqueStableKeys(draft.inputs)
  ) {
    return false;
  }

  const initialKeys = initialInputs.map((input) => input.rowKey);
  const persistedKeys = draft.inputs.map((input) => input.rowKey);
  return (
    persistedKeys.length === initialKeys.length &&
    initialKeys.every((key) => persistedKeys.includes(key))
  );
}

function normalizeInitialInputs(
  inputs: readonly SyntheticReviewInput[],
): readonly SyntheticReviewInput[] {
  if (!hasUniqueStableKeys(inputs) || !inputs.every(isReviewInput)) {
    throw new TypeError("Review draft inputs must use unique stable row keys and valid values");
  }
  return freezeInputs(inputs);
}

function persistedToSnapshot(
  persisted: PersistedReviewDraft,
  initialInputs: readonly SyntheticReviewInput[],
): SyntheticReviewDraftSnapshot {
  const persistedByKey = new Map(persisted.inputs.map((input) => [input.rowKey, input]));
  return freezeSnapshot(
    persisted.sessionKey,
    persisted.revision,
    initialInputs.map((input) => persistedByKey.get(input.rowKey) ?? input),
  );
}

function safeRead(
  storage: ReviewDraftStorage | null,
  key: string,
  sessionKey: string,
  initialInputs: readonly SyntheticReviewInput[],
): { snapshot: SyntheticReviewDraftSnapshot | null; available: boolean } {
  if (!storage) return { snapshot: null, available: false };

  let raw: string | null;
  try {
    raw = storage.getItem(key);
  } catch {
    // Storage access is an untrusted browser boundary.
    return { snapshot: null, available: false };
  }

  if (!raw) return { snapshot: null, available: true };

  try {
    const parsed: unknown = JSON.parse(raw);
    return {
      snapshot: isPersistedDraft(parsed, sessionKey, initialInputs)
        ? persistedToSnapshot(parsed, initialInputs)
        : null,
      available: true,
    };
  } catch {
    // Malformed or stale data is ignored; storage itself remains usable.
    return { snapshot: null, available: true };
  }
}

function safeWrite(
  storage: ReviewDraftStorage | null,
  key: string,
  snapshot: SyntheticReviewDraftSnapshot,
): boolean {
  if (!storage) return false;

  const persisted: PersistedReviewDraft = {
    schemaVersion: REVIEW_DRAFT_STORAGE_VERSION,
    sessionKey: snapshot.sessionKey,
    revision: snapshot.revision,
    inputs: snapshot.inputs,
  };

  try {
    storage.setItem(key, JSON.stringify(persisted));
    return true;
  } catch {
    // Quota/security errors must not discard the in-memory draft.
    return false;
  }
}

function isDraftStoreOptions(
  value: DraftStoreOptions | ReviewDraftStorage | null,
): value is DraftStoreOptions {
  return (
    value !== null &&
    typeof value === "object" &&
    ("storage" in value || "storageKey" in value)
  );
}

export function reviewDraftStorageKey(sessionKey: string): string {
  return `${REVIEW_DRAFT_STORAGE_PREFIX}${encodeURIComponent(sessionKey)}`;
}

/**
 * Revision-checked localStorage draft store with an in-memory fallback.
 * localStorage is an optional cache; the current draft remains usable when it
 * is missing, blocked, malformed, or full.
 */
export class LocalStorageSyntheticReviewDraftStore
  implements SyntheticReviewDraftStore
{
  private readonly sessionKey: string;
  private readonly initialInputs: readonly SyntheticReviewInput[];
  private readonly storage: ReviewDraftStorage | null;
  private readonly storageKey: string;
  private persistenceMode: DraftPersistenceStatus;
  private snapshot: SyntheticReviewDraftSnapshot;

  constructor(
    sessionKey: string,
    inputs: readonly SyntheticReviewInput[],
    optionsOrStorage: DraftStoreOptions | ReviewDraftStorage | null = {},
  ) {
    if (sessionKey.trim().length === 0) {
      throw new TypeError("Review draft session key must not be empty");
    }

    this.sessionKey = sessionKey;
    this.initialInputs = normalizeInitialInputs(inputs);
    const options = isDraftStoreOptions(optionsOrStorage) ? optionsOrStorage : {};
    this.storage = isDraftStoreOptions(optionsOrStorage)
      ? options.storage === undefined
        ? getDefaultStorage()
        : options.storage
    : optionsOrStorage ?? getDefaultStorage();
    this.storageKey = options.storageKey ?? reviewDraftStorageKey(sessionKey);
    this.persistenceMode = this.storage ? "persistent" : "memory";
    this.snapshot = freezeSnapshot(sessionKey, 1, this.initialInputs);

    const persisted = safeRead(this.storage, this.storageKey, sessionKey, this.initialInputs);
    if (!persisted.available) this.persistenceMode = "memory";
    if (persisted.snapshot) this.snapshot = persisted.snapshot;
  }

  get persistenceStatus(): DraftPersistenceStatus {
    return this.persistenceMode;
  }

  read(): SyntheticReviewDraftSnapshot {
    const persisted = safeRead(this.storage, this.storageKey, this.sessionKey, this.initialInputs);
    if (!persisted.available) this.persistenceMode = "memory";
    if (persisted.snapshot && persisted.snapshot.revision >= this.snapshot.revision) {
      this.snapshot = persisted.snapshot;
    }
    return this.snapshot;
  }

  commitDraft(
    expectedRevision: number,
    inputs: readonly SyntheticReviewInput[],
  ): CommitDraftResult {
    const current = this.read();
    if (expectedRevision !== current.revision) {
      return { status: "conflict", current };
    }
    if (current.revision >= Number.MAX_SAFE_INTEGER) {
      throw new RangeError("REVIEW_DRAFT_REVISION_EXHAUSTED");
    }

    const nextInputs = normalizeInitialInputs(inputs);
    const next = freezeSnapshot(this.sessionKey, current.revision + 1, nextInputs);
    this.snapshot = next;
    if (!safeWrite(this.storage, this.storageKey, next)) this.persistenceMode = "memory";
    return { status: "saved", snapshot: next };
  }
}
