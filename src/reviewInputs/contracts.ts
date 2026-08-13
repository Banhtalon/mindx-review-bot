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
