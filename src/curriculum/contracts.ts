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
