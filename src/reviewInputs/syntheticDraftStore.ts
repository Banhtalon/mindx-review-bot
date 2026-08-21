import type {
  CommitDraftResult,
  SyntheticReviewDraftSnapshot,
  SyntheticReviewDraftStore,
  SyntheticReviewInput,
} from "./contracts";

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

export class InMemorySyntheticReviewDraftStore
  implements SyntheticReviewDraftStore
{
  private snapshot: SyntheticReviewDraftSnapshot;

  constructor(
    sessionKey: string,
    inputs: readonly SyntheticReviewInput[],
  ) {
    this.snapshot = freezeSnapshot(sessionKey, 1, inputs);
  }

  read(): SyntheticReviewDraftSnapshot {
    return this.snapshot;
  }

  commitDraft(
    expectedRevision: number,
    inputs: readonly SyntheticReviewInput[],
  ): CommitDraftResult {
    if (expectedRevision !== this.snapshot.revision) {
      return { status: "conflict", current: this.snapshot };
    }

    this.snapshot = freezeSnapshot(
      this.snapshot.sessionKey,
      this.snapshot.revision + 1,
      inputs,
    );
    return { status: "saved", snapshot: this.snapshot };
  }

  injectExternalRevisionForTest(
    inputs: readonly SyntheticReviewInput[],
  ): SyntheticReviewDraftSnapshot {
    this.snapshot = freezeSnapshot(
      this.snapshot.sessionKey,
      this.snapshot.revision + 1,
      inputs,
    );
    return this.snapshot;
  }
}
