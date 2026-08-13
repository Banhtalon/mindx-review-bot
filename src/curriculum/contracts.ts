export type CurriculumEntryInput = {
  readonly sessionNumber: number;
  readonly lessonTitle: string;
  readonly lessonContent: readonly string[];
  readonly homeworkTitle?: string | null;
};

export type CourseCatalogInput = {
  readonly courseCode: string;
  readonly courseName: string;
  readonly totalSessions: number;
  readonly entries: readonly CurriculumEntryInput[];
};

export type CurriculumEntry = {
  readonly sessionNumber: number;
  readonly lessonTitle: string;
  readonly lessonContent: readonly string[];
  readonly homeworkTitle?: string;
};

export type CourseCatalog = {
  readonly courseCode: string;
  readonly courseName: string;
  readonly totalSessions: number;
  readonly entries: readonly CurriculumEntry[];
};

export type SyntheticSession = {
  readonly id: string;
  readonly classCode: string;
  readonly courseCode: string;
  readonly sessionNumber: number;
  readonly scheduledDate: string;
  readonly startTime: string;
  readonly endTime: string;
  readonly workflowStatus: "context_pending" | "context_ready";
};

export type LessonContextStatus =
  | "matched"
  | "no_next_session"
  | "curriculum_missing"
  | "manual_fallback";

export type LessonContextReasonCode =
  | "LESSON_CONTEXT_MATCH"
  | "NO_NEXT_SESSION"
  | "CURRICULUM_MISSING"
  | "COURSE_NOT_FOUND"
  | "COURSE_AMBIGUOUS"
  | "SESSION_CONTEXT_INVALID"
  | "NEXT_SESSION_AMBIGUOUS";

export type LessonContextWarningCode = "NEXT_CURRICULUM_MISSING";

export type LessonContextResolution = {
  readonly status: LessonContextStatus;
  readonly reasonCode: LessonContextReasonCode;
  readonly session: SyntheticSession;
  readonly currentLesson?: CurriculumEntry;
  readonly nextSession?: SyntheticSession;
  readonly nextLesson?: CurriculumEntry;
  readonly warnings: readonly LessonContextWarningCode[];
};

export type CurriculumIssueCode =
  | "COURSE_CODE_REQUIRED"
  | "COURSE_NAME_REQUIRED"
  | "TOTAL_SESSIONS_INVALID"
  | "SESSION_NUMBER_INVALID"
  | "SESSION_NUMBER_OUT_OF_RANGE"
  | "SESSION_NUMBER_DUPLICATE"
  | "LESSON_TITLE_REQUIRED"
  | "LESSON_CONTENT_REQUIRED";

export type CurriculumIssue = {
  readonly code: CurriculumIssueCode;
  readonly path: string;
};

export type CurriculumValidationResult =
  | { readonly ok: true; readonly catalog: CourseCatalog }
  | { readonly ok: false; readonly issues: readonly CurriculumIssue[] };

export function normalizeCourseCode(value: string): string {
  return value.normalize("NFC").replace(/\s+/g, " ").trim().toLocaleUpperCase();
}
