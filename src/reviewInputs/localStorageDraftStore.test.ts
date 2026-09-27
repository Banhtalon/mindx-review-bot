import { describe, expect, it } from "vitest";

import {
  createInitialReviewInputs,
  PHASE5B_SYNTHETIC_LEARNERS,
} from "../fixtures/phase5bReviewInputs";
import {
  LocalStorageSyntheticReviewDraftStore,
  REVIEW_DRAFT_STORAGE_VERSION,
  reviewDraftStorageKey,
} from "./localStorageDraftStore";

function createStorage() {
  const values = new Map<string, string>();
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    values,
  };
}

function createInputs() {
  return createInitialReviewInputs(PHASE5B_SYNTHETIC_LEARNERS);
}

describe("LocalStorageSyntheticReviewDraftStore", () => {
  it("persists a versioned snapshot and restores it in a new store", () => {
    const storage = createStorage();
    const first = new LocalStorageSyntheticReviewDraftStore(
      "synthetic-robotics-session-3",
      createInputs(),
      { storage },
    );
    const changed = first.read().inputs.map((input) =>
      input.rowKey === "synthetic-review-001"
        ? { ...input, attendance: "present" as const, noteDraft: "Ready" }
        : input,
    );

    expect(first.commitDraft(1, changed).status).toBe("saved");

    const raw = storage.values.get(reviewDraftStorageKey("synthetic-robotics-session-3"));
    expect(raw).toBeDefined();
    expect(JSON.parse(raw!).schemaVersion).toBe(REVIEW_DRAFT_STORAGE_VERSION);

    const restored = new LocalStorageSyntheticReviewDraftStore(
      "synthetic-robotics-session-3",
      createInputs(),
      { storage },
    );
    const restoredSnapshot = restored.read();
    expect(restoredSnapshot.revision).toBe(2);
    expect(restoredSnapshot.inputs[0]).toMatchObject({
      rowKey: "synthetic-review-001",
      attendance: "present",
      noteDraft: "Ready",
    });
  });

  it("falls back to memory when storage access throws", () => {
    const throwingStorage = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    };
    const store = new LocalStorageSyntheticReviewDraftStore(
      "synthetic-robotics-session-3",
      createInputs(),
      { storage: throwingStorage },
    );
    expect(store.persistenceStatus).toBe("memory");
    const changed = store.read().inputs.map((input) => ({ ...input, attendance: "absent" as const }));

    expect(store.commitDraft(1, changed)).toMatchObject({ status: "saved", snapshot: { revision: 2 } });
    expect(store.persistenceStatus).toBe("memory");
    expect(store.read().inputs.every((input) => input.attendance === "absent")).toBe(true);
  });

  it("ignores malformed, incompatible, or mismatched persisted drafts", () => {
    const storage = createStorage();
    const key = reviewDraftStorageKey("synthetic-robotics-session-3");
    storage.values.set(key, JSON.stringify({
      schemaVersion: 999,
      sessionKey: "synthetic-robotics-session-3",
      revision: 9,
      inputs: [],
    }));

    const store = new LocalStorageSyntheticReviewDraftStore(
      "synthetic-robotics-session-3",
      createInputs(),
      { storage },
    );

    expect(store.read().revision).toBe(1);
    expect(store.persistenceStatus).toBe("persistent");
    expect(store.read().inputs).toEqual(createInputs());
  });

  it("rejects a stale commit after another store has advanced the revision", () => {
    const storage = createStorage();
    const first = new LocalStorageSyntheticReviewDraftStore("session", createInputs(), { storage });
    const second = new LocalStorageSyntheticReviewDraftStore("session", createInputs(), { storage });
    const changed = second.read().inputs.map((input) => ({ ...input, attendance: "present" as const }));
    second.commitDraft(1, changed);

    const result = first.commitDraft(1, first.read().inputs);
    expect(result).toMatchObject({ status: "conflict", current: { revision: 2 } });
  });

  it("does not overflow the revision counter", () => {
    const storage = createStorage();
    const sessionKey = "revision-limit";
    storage.values.set(reviewDraftStorageKey(sessionKey), JSON.stringify({
      schemaVersion: REVIEW_DRAFT_STORAGE_VERSION,
      sessionKey,
      revision: Number.MAX_SAFE_INTEGER,
      inputs: createInputs(),
    }));
    const store = new LocalStorageSyntheticReviewDraftStore(sessionKey, createInputs(), { storage });

    expect(() => store.commitDraft(Number.MAX_SAFE_INTEGER, createInputs())).toThrow(
      "REVIEW_DRAFT_REVISION_EXHAUSTED",
    );
  });

  it("rejects a draft note longer than the hosted input limit", () => {
    const store = new LocalStorageSyntheticReviewDraftStore("note-limit", createInputs(), {
      storage: createStorage(),
    });
    const oversized = store.read().inputs.map((input, index) =>
      index === 0 ? { ...input, noteDraft: "x".repeat(10_001) } : input,
    );

    expect(() => store.commitDraft(1, oversized)).toThrow(
      "Review draft inputs must use unique stable row keys and valid values",
    );
  });
});
