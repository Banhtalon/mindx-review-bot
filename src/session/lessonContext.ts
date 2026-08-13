import {
  normalizeCourseCode,
  type CourseCatalog,
  type LessonContextReasonCode,
  type LessonContextResolution,
  type SyntheticSession,
} from "../curriculum/contracts";

function normalizeClassCode(value: string): string {
  return value.normalize("NFC").replace(/\s+/g, " ").trim().toLocaleUpperCase();
}

function isValidIsoLocalDate(value: string): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);

  if (!match) {
    return false;
  }

  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(Date.UTC(year, month - 1, day));

  return date.getUTCFullYear() === year
    && date.getUTCMonth() === month - 1
    && date.getUTCDate() === day;
}

function isValidTime(value: string): boolean {
  const match = /^(\d{2}):(\d{2})$/.exec(value);

  if (!match) {
    return false;
  }

  const hour = Number(match[1]);
  const minute = Number(match[2]);

  return hour >= 0 && hour <= 23 && minute >= 0 && minute <= 59;
}

function hasValidSessionContext(session: SyntheticSession): boolean {
  return Number.isInteger(session.sessionNumber)
    && session.sessionNumber > 0
    && isValidIsoLocalDate(session.scheduledDate)
    && isValidTime(session.startTime)
    && isValidTime(session.endTime);
}

function buildResult(
  session: SyntheticSession,
  reasonCode: LessonContextReasonCode,
  overrides: Omit<Partial<LessonContextResolution>, "session" | "reasonCode"> = {},
): LessonContextResolution {
  return {
    status: "manual_fallback",
    warnings: [],
    session,
    reasonCode,
    ...overrides,
  };
}

export function resolveLessonContext(
  selectedSession: SyntheticSession,
  sessions: readonly SyntheticSession[],
  catalogs: readonly CourseCatalog[],
): LessonContextResolution {
  if (!hasValidSessionContext(selectedSession)) {
    return buildResult(selectedSession, "SESSION_CONTEXT_INVALID");
  }

  const matchingCatalogs = catalogs.filter(
    (catalog) => normalizeCourseCode(catalog.courseCode) === normalizeCourseCode(selectedSession.courseCode),
  );

  if (matchingCatalogs.length === 0) {
    return buildResult(selectedSession, "COURSE_NOT_FOUND");
  }

  if (matchingCatalogs.length > 1) {
    return buildResult(selectedSession, "COURSE_AMBIGUOUS");
  }

  const catalog = matchingCatalogs[0];
  const currentLesson = catalog.entries.find(
    (entry) => entry.sessionNumber === selectedSession.sessionNumber,
  );

  if (!currentLesson) {
    return buildResult(selectedSession, "CURRICULUM_MISSING", {
      status: "curriculum_missing",
    });
  }

  const matchingSessions = sessions.filter(
    (session) => normalizeClassCode(session.classCode) === normalizeClassCode(selectedSession.classCode)
      && normalizeCourseCode(session.courseCode) === normalizeCourseCode(selectedSession.courseCode),
  );

  if (!matchingSessions.every(hasValidSessionContext)) {
    return buildResult(selectedSession, "SESSION_CONTEXT_INVALID");
  }

  const laterSessions = matchingSessions
    .filter((session) => (
      `${session.scheduledDate}|${session.startTime}|${session.endTime}|${session.id}`
        > `${selectedSession.scheduledDate}|${selectedSession.startTime}|${selectedSession.endTime}|${selectedSession.id}`
    ))
    .sort((left, right) => {
      const leftKey = `${left.scheduledDate}|${left.startTime}|${left.endTime}|${left.id}`;
      const rightKey = `${right.scheduledDate}|${right.startTime}|${right.endTime}|${right.id}`;
      return leftKey.localeCompare(rightKey);
    });

  if (laterSessions.length === 0) {
    return buildResult(selectedSession, "NO_NEXT_SESSION", {
      status: "no_next_session",
      currentLesson,
    });
  }

  const nextSession = laterSessions[0];

  if (
    laterSessions.length > 1
    && laterSessions[1].id !== nextSession.id
    && laterSessions[1].scheduledDate === nextSession.scheduledDate
    && laterSessions[1].startTime === nextSession.startTime
  ) {
    return buildResult(selectedSession, "NEXT_SESSION_AMBIGUOUS", {
      currentLesson,
    });
  }

  const nextLesson = catalog.entries.find((entry) => entry.sessionNumber === nextSession.sessionNumber);

  if (!nextLesson) {
    return {
      status: "matched",
      reasonCode: "LESSON_CONTEXT_MATCH",
      session: selectedSession,
      currentLesson,
      nextSession,
      warnings: ["NEXT_CURRICULUM_MISSING"],
    };
  }

  return {
    status: "matched",
    reasonCode: "LESSON_CONTEXT_MATCH",
    session: selectedSession,
    currentLesson,
    nextSession,
    nextLesson,
    warnings: [],
  };
}
