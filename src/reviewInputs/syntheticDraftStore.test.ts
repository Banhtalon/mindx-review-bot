import { describe, expect, it } from "vitest";

import {
  createInitialReviewInputs,
  PHASE5B_SYNTHETIC_LEARNERS,
} from "../fixtures/phase5bReviewInputs";
import { InMemorySyntheticReviewDraftStore } from "./syntheticDraftStore";

const createStore = () =>
  new InMemorySyntheticReviewDraftStore(
    "synthetic-robotics-session-3",
    createInitialReviewInputs(PHASE5B_SYNTHETIC_LEARNERS),
  );

describe("InMemorySyntheticReviewDraftStore", () => {
  it("starts at revision one with an immutable synthetic snapshot", () => {
    const snapshot = createStore().read();

    expect(snapshot.sessionKey).toBe("synthetic-robotics-session-3");
    expect(snapshot.revision).toBe(1);
    expect(snapshot.inputs).toHaveLength(3);
    expect(Object.isFrozen(snapshot)).toBe(true);
    expect(Object.isFrozen(snapshot.inputs)).toBe(true);
    expect(snapshot.inputs.every(Object.isFrozen)).toBe(true);
  });

  it("commits against the current revision and increments exactly once", () => {
    const store = createStore();
    const changed = store.read().inputs.map((input) =>
      input.rowKey === "synthetic-review-001"
        ? { ...input, attendance: "present" as const }
        : input,
    );

    const result = store.commitDraft(1, changed);

    expect(result.status).toBe("saved");
    expect(store.read().revision).toBe(2);
    expect(store.read().inputs[0].attendance).toBe("present");
  });

  it("rejects a stale revision without replacing the current snapshot", () => {
    const store = createStore();
    const external = store.read().inputs.map((input) =>
      input.rowKey === "synthetic-review-001"
        ? { ...input, noteDraft: "External synthetic revision" }
        : input,
    );
    store.injectExternalRevisionForTest(external);

    const staleLocal = store.read().inputs.map((input) =>
      input.rowKey === "synthetic-review-001"
        ? { ...input, noteDraft: "Stale local synthetic draft" }
        : input,
    );
    const result = store.commitDraft(1, staleLocal);

    expect(result).toMatchObject({ status: "conflict" });
    expect(store.read().revision).toBe(2);
    expect(store.read().inputs[0].noteDraft).toBe("External synthetic revision");
  });
});
