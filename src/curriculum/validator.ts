import {
  normalizeCourseCode,
  type CourseCatalog,
  type CourseCatalogInput,
  type CurriculumIssue,
  type CurriculumValidationResult,
} from "./contracts";

function normalizeText(value: string): string {
  return value.normalize("NFC").replace(/\s+/g, " ").trim();
}

export function validateCourseCatalog(
  input: CourseCatalogInput,
): CurriculumValidationResult {
  const catalog: CourseCatalog = {
    courseCode: normalizeCourseCode(input.courseCode),
    courseName: normalizeText(input.courseName),
    totalSessions: input.totalSessions,
    entries: input.entries.map((entry) => {
      const homeworkTitle = entry.homeworkTitle == null
        ? undefined
        : normalizeText(entry.homeworkTitle);

      return {
        sessionNumber: entry.sessionNumber,
        lessonTitle: normalizeText(entry.lessonTitle),
        lessonContent: entry.lessonContent
          .map(normalizeText)
          .filter((content) => content.length > 0),
        ...(homeworkTitle ? { homeworkTitle } : {}),
      };
    }),
  };

  const issues: CurriculumIssue[] = [];

  if (catalog.courseCode.length === 0) {
    issues.push({ code: "COURSE_CODE_REQUIRED", path: "courseCode" });
  }

  if (catalog.courseName.length === 0) {
    issues.push({ code: "COURSE_NAME_REQUIRED", path: "courseName" });
  }

  if (!Number.isInteger(catalog.totalSessions) || catalog.totalSessions <= 0) {
    issues.push({ code: "TOTAL_SESSIONS_INVALID", path: "totalSessions" });
  }

  const seenSessionNumbers = new Set<number>();

  catalog.entries.forEach((entry, index) => {
    const sessionPath = `entries[${index}].sessionNumber`;
    const lessonTitlePath = `entries[${index}].lessonTitle`;
    const lessonContentPath = `entries[${index}].lessonContent`;

    if (!Number.isInteger(entry.sessionNumber)) {
      issues.push({ code: "SESSION_NUMBER_INVALID", path: sessionPath });
    } else if (entry.sessionNumber < 1 || entry.sessionNumber > catalog.totalSessions) {
      issues.push({ code: "SESSION_NUMBER_OUT_OF_RANGE", path: sessionPath });
    } else if (seenSessionNumbers.has(entry.sessionNumber)) {
      issues.push({ code: "SESSION_NUMBER_DUPLICATE", path: sessionPath });
    } else {
      seenSessionNumbers.add(entry.sessionNumber);
    }

    if (entry.lessonTitle.length === 0) {
      issues.push({ code: "LESSON_TITLE_REQUIRED", path: lessonTitlePath });
    }

    if (entry.lessonContent.length === 0) {
      issues.push({ code: "LESSON_CONTENT_REQUIRED", path: lessonContentPath });
    }
  });

  return issues.length > 0 ? { ok: false, issues } : { ok: true, catalog };
}
