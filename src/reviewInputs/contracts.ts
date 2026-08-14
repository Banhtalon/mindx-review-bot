export type AttendanceStatus = "present" | "absent" | "unknown";

export type LearningLevel = "strong" | "developing" | "needs_support" | "unknown";

export type SyntheticLearner = {
  readonly rowKey: string;
  readonly displayName: string;
};

export type SyntheticReviewInput = {
  readonly rowKey: string;
  readonly attendance: AttendanceStatus;
  readonly level: LearningLevel;
  readonly noteDraft: string;
};

export type ReviewInputGate =
  | {
      readonly ready: true;
      readonly reasonCode: "ATTENDANCE_COMPLETE";
      readonly unknownAttendanceRowKeys: readonly [];
    }
  | {
      readonly ready: false;
      readonly reasonCode: "ATTENDANCE_UNKNOWN";
      readonly unknownAttendanceRowKeys: readonly string[];
    };

export type SyntheticReviewDraftSnapshot = {
  readonly sessionKey: string;
  readonly revision: number;
  readonly inputs: readonly SyntheticReviewInput[];
};

export type CommitDraftResult =
  | {
      readonly status: "saved";
      readonly snapshot: SyntheticReviewDraftSnapshot;
    }
  | {
      readonly status: "conflict";
      readonly current: SyntheticReviewDraftSnapshot;
    };

export interface SyntheticReviewDraftStore {
  read(): SyntheticReviewDraftSnapshot;
  commitDraft(
    expectedRevision: number,
    inputs: readonly SyntheticReviewInput[],
  ): CommitDraftResult;
}
