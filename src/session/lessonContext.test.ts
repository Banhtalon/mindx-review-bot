import { describe, expect, it } from "vitest";
import type { CourseCatalog, SyntheticSession } from "../curriculum/contracts";
import { resolveLessonContext } from "./lessonContext";

const catalogs: readonly CourseCatalog[] = [
  {
    courseCode: "JSB",
    courseName: "Synthetic Web Developer Basic",
    totalSessions: 5,
    entries: [
      {
        sessionNumber: 5,
        lessonTitle: "Synthetic session five",
        lessonContent: ["Synthetic content five"],
      },
      {
        sessionNumber: 1,
        lessonTitle: "Synthetic session one",
        lessonContent: ["Synthetic content one"],
      },
      {
        sessionNumber: 3,
        lessonTitle: "Synthetic session three",
        lessonContent: ["Synthetic content three"],
      },
    ],
  },
];

const selectedSession: SyntheticSession = {
  id: "session-003",
  classCode: "SYN-CLASS-01",
  courseCode: "jsb",
  sessionNumber: 3,
  scheduledDate: "2026-08-13",
  startTime: "19:00",
  endTime: "20:30",
  workflowStatus: "context_pending",
};

describe("synthetic lesson context resolution", () => {
  it("finds current lesson by explicit session number", () => {
    const result = resolveLessonContext(selectedSession, [selectedSession], catalogs);

    expect(result.currentLesson?.sessionNumber).toBe(3);
    expect(result.currentLesson?.lessonTitle).toBe("Synthetic session three");
  });

  it("returns course_not_found when no normalized catalog matches", () => {
    const result = resolveLessonContext(
      { ...selectedSession, courseCode: "PYB" },
      [selectedSession],
      catalogs,
    );

    expect(result).toMatchObject({
      status: "manual_fallback",
      reasonCode: "COURSE_NOT_FOUND",
      warnings: [],
    });
  });

  it("returns course_ambiguous when more than one normalized catalog matches", () => {
    const result = resolveLessonContext(selectedSession, [selectedSession], [
      catalogs[0],
      {
        ...catalogs[0],
        courseCode: " jsb ",
        courseName: "Synthetic Web Developer Basic Duplicate",
      },
    ]);

    expect(result).toMatchObject({
      status: "manual_fallback",
      reasonCode: "COURSE_AMBIGUOUS",
      warnings: [],
    });
  });

  it("returns curriculum_missing when the selected session has no curriculum entry", () => {
    const result = resolveLessonContext(
      { ...selectedSession, sessionNumber: 2 },
      [{ ...selectedSession, sessionNumber: 2 }],
      catalogs,
    );

    expect(result).toMatchObject({
      status: "curriculum_missing",
      reasonCode: "CURRICULUM_MISSING",
      warnings: [],
    });
  });

  it("chooses the earliest later actual session even when the number is non-consecutive", () => {
    const sessions: readonly SyntheticSession[] = [
      selectedSession,
      {
        ...selectedSession,
        id: "session-007",
        sessionNumber: 7,
        scheduledDate: "2026-08-20",
        startTime: "19:00",
        endTime: "20:30",
      },
      {
        ...selectedSession,
        id: "session-005",
        sessionNumber: 5,
        scheduledDate: "2026-08-15",
        startTime: "18:30",
        endTime: "20:00",
      },
    ];

    const result = resolveLessonContext(selectedSession, sessions, catalogs);

    expect(result).toMatchObject({
      status: "matched",
      reasonCode: "LESSON_CONTEXT_MATCH",
      nextSession: {
        id: "session-005",
        sessionNumber: 5,
      },
      nextLesson: {
        sessionNumber: 5,
        lessonTitle: "Synthetic session five",
      },
      warnings: [],
    });
  });

  it("returns no_next_session for the final actual session", () => {
    const finalSession: SyntheticSession = {
      ...selectedSession,
      id: "session-005",
      sessionNumber: 5,
      scheduledDate: "2026-08-15",
      startTime: "18:30",
      endTime: "20:00",
    };

    const result = resolveLessonContext(finalSession, [selectedSession, finalSession], catalogs);

    expect(result).toMatchObject({
      status: "no_next_session",
      reasonCode: "NO_NEXT_SESSION",
      currentLesson: {
        sessionNumber: 5,
        lessonTitle: "Synthetic session five",
      },
      warnings: [],
    });
    expect(result.nextSession).toBeUndefined();
    expect(result.nextLesson).toBeUndefined();
  });

  it("returns the actual next session with a warning when its curriculum is missing", () => {
    const sessions: readonly SyntheticSession[] = [
      selectedSession,
      {
        ...selectedSession,
        id: "session-004",
        sessionNumber: 4,
        scheduledDate: "2026-08-14",
        startTime: "19:00",
        endTime: "20:30",
      },
    ];

    const result = resolveLessonContext(selectedSession, sessions, catalogs);

    expect(result).toMatchObject({
      status: "matched",
      reasonCode: "LESSON_CONTEXT_MATCH",
      nextSession: {
        id: "session-004",
        sessionNumber: 4,
      },
      warnings: ["NEXT_CURRICULUM_MISSING"],
    });
    expect(result.nextLesson).toBeUndefined();
  });

  it("fails closed when two later sessions share the earliest timestamp", () => {
    const sessions: readonly SyntheticSession[] = [
      selectedSession,
      {
        ...selectedSession,
        id: "session-005a",
        sessionNumber: 5,
        scheduledDate: "2026-08-15",
        startTime: "18:30",
        endTime: "20:00",
      },
      {
        ...selectedSession,
        id: "session-005b",
        sessionNumber: 6,
        scheduledDate: "2026-08-15",
        startTime: "18:30",
        endTime: "20:30",
      },
    ];

    const result = resolveLessonContext(selectedSession, sessions, catalogs);

    expect(result).toMatchObject({
      status: "manual_fallback",
      reasonCode: "NEXT_SESSION_AMBIGUOUS",
      warnings: [],
    });
  });

  it("fails closed when a same-slot duplicate differs only by end time or id", () => {
    const sessions: readonly SyntheticSession[] = [
      selectedSession,
      {
        ...selectedSession,
        id: "session-003-duplicate",
        sessionNumber: 4,
        endTime: "21:00",
      },
      {
        ...selectedSession,
        id: "session-005",
        sessionNumber: 5,
        scheduledDate: "2026-08-15",
        startTime: "18:30",
        endTime: "20:00",
      },
    ];

    const result = resolveLessonContext(selectedSession, sessions, catalogs);

    expect(result).toMatchObject({
      status: "manual_fallback",
      reasonCode: "NEXT_SESSION_AMBIGUOUS",
      warnings: [],
    });
    expect(result.nextSession).toBeUndefined();
    expect(result.nextLesson).toBeUndefined();
  });

  it("rejects malformed date or time context", () => {
    expect(resolveLessonContext({
      ...selectedSession,
      scheduledDate: "2026-13-40",
    }, [selectedSession], catalogs)).toMatchObject({
      status: "manual_fallback",
      reasonCode: "SESSION_CONTEXT_INVALID",
      warnings: [],
    });

    expect(resolveLessonContext(selectedSession, [
      selectedSession,
      {
        ...selectedSession,
        id: "session-005",
        sessionNumber: 5,
        scheduledDate: "2026-08-15",
        startTime: "99:30",
        endTime: "20:00",
      },
    ], catalogs)).toMatchObject({
      status: "manual_fallback",
      reasonCode: "SESSION_CONTEXT_INVALID",
      warnings: [],
    });
  });
});
