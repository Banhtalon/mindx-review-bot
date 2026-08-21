import { describe, expect, it } from "vitest";
import { validateCourseCatalog } from "./validator";

describe("synthetic curriculum catalog validation", () => {
  it("normalizes course text, lesson text, content, and homework", () => {
    const result = validateCourseCatalog({
      courseCode: "  jsb  ",
      courseName: "  Synthetic Web Developer Basic  ",
      totalSessions: 3,
      entries: [
        {
          sessionNumber: 1,
          lessonTitle: "  Intro to HTML  ",
          lessonContent: ["  HTML tags  ", "   ", " Semantic layout "],
          homeworkTitle: "  Finish synthetic landing page  ",
        },
      ],
    });

    expect(result).toEqual({
      ok: true,
      catalog: {
        courseCode: "JSB",
        courseName: "Synthetic Web Developer Basic",
        totalSessions: 3,
        entries: [
          {
            sessionNumber: 1,
            lessonTitle: "Intro to HTML",
            lessonContent: ["HTML tags", "Semantic layout"],
            homeworkTitle: "Finish synthetic landing page",
          },
        ],
      },
    });
  });

  it("rejects blank course code and name", () => {
    const result = validateCourseCatalog({
      courseCode: "   ",
      courseName: "   ",
      totalSessions: 3,
      entries: [],
    });

    expect(result).toEqual({
      ok: false,
      issues: [
        { code: "COURSE_CODE_REQUIRED", path: "courseCode" },
        { code: "COURSE_NAME_REQUIRED", path: "courseName" },
      ],
    });
  });

  it("rejects a non-positive or fractional total", () => {
    expect(validateCourseCatalog({
      courseCode: "JSB",
      courseName: "Synthetic Web Developer Basic",
      totalSessions: 0,
      entries: [],
    })).toEqual({
      ok: false,
      issues: [{ code: "TOTAL_SESSIONS_INVALID", path: "totalSessions" }],
    });

    expect(validateCourseCatalog({
      courseCode: "JSB",
      courseName: "Synthetic Web Developer Basic",
      totalSessions: 1.5,
      entries: [],
    })).toEqual({
      ok: false,
      issues: [{ code: "TOTAL_SESSIONS_INVALID", path: "totalSessions" }],
    });
  });

  it("rejects out-of-range and duplicate session numbers", () => {
    const result = validateCourseCatalog({
      courseCode: "JSB",
      courseName: "Synthetic Web Developer Basic",
      totalSessions: 3,
      entries: [
        {
          sessionNumber: 4,
          lessonTitle: "Synthetic lesson one",
          lessonContent: ["Synthetic content"],
        },
        {
          sessionNumber: 2,
          lessonTitle: "Synthetic lesson two",
          lessonContent: ["Synthetic content"],
        },
        {
          sessionNumber: 2,
          lessonTitle: "Synthetic lesson three",
          lessonContent: ["Synthetic content"],
        },
      ],
    });

    expect(result).toEqual({
      ok: false,
      issues: [
        { code: "SESSION_NUMBER_OUT_OF_RANGE", path: "entries[0].sessionNumber" },
        { code: "SESSION_NUMBER_DUPLICATE", path: "entries[2].sessionNumber" },
      ],
    });
  });

  it("rejects a non-integer or NaN session number", () => {
    expect(validateCourseCatalog({
      courseCode: "JSB",
      courseName: "Synthetic Web Developer Basic",
      totalSessions: 3,
      entries: [
        {
          sessionNumber: 1.5,
          lessonTitle: "Synthetic lesson one",
          lessonContent: ["Synthetic content"],
        },
      ],
    })).toEqual({
      ok: false,
      issues: [
        { code: "SESSION_NUMBER_INVALID", path: "entries[0].sessionNumber" },
      ],
    });

    expect(validateCourseCatalog({
      courseCode: "JSB",
      courseName: "Synthetic Web Developer Basic",
      totalSessions: 3,
      entries: [
        {
          sessionNumber: Number.NaN,
          lessonTitle: "Synthetic lesson two",
          lessonContent: ["Synthetic content"],
        },
      ],
    })).toEqual({
      ok: false,
      issues: [
        { code: "SESSION_NUMBER_INVALID", path: "entries[0].sessionNumber" },
      ],
    });
  });

  it("rejects blank lesson title and empty lesson content", () => {
    const result = validateCourseCatalog({
      courseCode: "JSB",
      courseName: "Synthetic Web Developer Basic",
      totalSessions: 3,
      entries: [
        {
          sessionNumber: 1,
          lessonTitle: "   ",
          lessonContent: ["   ", ""],
        },
      ],
    });

    expect(result).toEqual({
      ok: false,
      issues: [
        { code: "LESSON_TITLE_REQUIRED", path: "entries[0].lessonTitle" },
        { code: "LESSON_CONTENT_REQUIRED", path: "entries[0].lessonContent" },
      ],
    });
  });

  it("allows an incomplete catalog by omitting absent session entries", () => {
    const result = validateCourseCatalog({
      courseCode: "JSB",
      courseName: "Synthetic Web Developer Basic",
      totalSessions: 5,
      entries: [
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
    });

    expect(result).toEqual({
      ok: true,
      catalog: {
        courseCode: "JSB",
        courseName: "Synthetic Web Developer Basic",
        totalSessions: 5,
        entries: [
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
    });
  });
});
