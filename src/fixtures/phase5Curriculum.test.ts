import { describe, expect, it } from "vitest";
import type { CourseCatalog, SyntheticSession } from "../curriculum/contracts";
import { validateCourseCatalog } from "../curriculum/validator";
import {
  PHASE5_COURSE_CATALOGS,
  PHASE5_SESSIONS,
} from "./phase5Curriculum";

describe("phase 5 synthetic curriculum fixtures", () => {
  it("contains valid synthetic catalogs and sessions", () => {
    expect(PHASE5_COURSE_CATALOGS).toHaveLength(2);
    expect(PHASE5_SESSIONS).toHaveLength(3);

    for (const catalog of PHASE5_COURSE_CATALOGS) {
      expect(validateCourseCatalog(catalog).ok).toBe(true);
    }

    expect(PHASE5_COURSE_CATALOGS).toContainEqual(
      expect.objectContaining({
        courseCode: "SYN-ROBOTICS-FOUNDATION",
        totalSessions: 5,
        entries: expect.arrayContaining([
          expect.objectContaining({ sessionNumber: 5 }),
          expect.objectContaining({ sessionNumber: 1 }),
          expect.objectContaining({ sessionNumber: 3 }),
        ]),
      }),
    );

    expect(PHASE5_COURSE_CATALOGS).toContainEqual(
      expect.objectContaining({
        courseCode: "SYN-PYTHON-FOUNDATION",
        totalSessions: 3,
        entries: expect.arrayContaining([
          expect.objectContaining({ sessionNumber: 1 }),
          expect.objectContaining({ sessionNumber: 3 }),
        ]),
      }),
    );

    expect(
      PHASE5_COURSE_CATALOGS.find((catalog) => catalog.courseCode === "SYN-PYTHON-FOUNDATION")
        ?.entries.some((entry) => entry.sessionNumber === 2),
    ).toBe(false);

    expect(PHASE5_SESSIONS).toContainEqual(
      expect.objectContaining({
        id: "synthetic-robotics-session-3",
        classCode: "SYN-ROBOTICS-01",
        courseCode: "SYN-ROBOTICS-FOUNDATION",
        sessionNumber: 3,
        scheduledDate: "2026-08-11",
        startTime: "19:00",
        endTime: "20:30",
        workflowStatus: "context_pending",
      }),
    );

    expect(PHASE5_SESSIONS).toContainEqual(
      expect.objectContaining({
        id: "synthetic-robotics-session-5",
        classCode: "SYN-ROBOTICS-01",
        courseCode: "SYN-ROBOTICS-FOUNDATION",
        sessionNumber: 5,
        scheduledDate: "2026-08-25",
        startTime: "19:00",
        endTime: "20:30",
        workflowStatus: "context_pending",
      }),
    );

    expect(PHASE5_SESSIONS).toContainEqual(
      expect.objectContaining({
        id: "synthetic-python-session-2",
        classCode: "SYN-PYTHON-02",
        courseCode: "SYN-PYTHON-FOUNDATION",
        sessionNumber: 2,
        scheduledDate: "2026-08-12",
        startTime: "18:00",
        endTime: "19:30",
        workflowStatus: "context_pending",
      }),
    );
  });

  it("freezes exported fixture arrays and nested values at runtime", () => {
    const roboticsCatalog = PHASE5_COURSE_CATALOGS[0];
    const roboticsEntry = roboticsCatalog.entries[0];
    const roboticsSession = PHASE5_SESSIONS[0];

    expect(Object.isFrozen(PHASE5_COURSE_CATALOGS)).toBe(true);
    expect(Object.isFrozen(roboticsCatalog)).toBe(true);
    expect(Object.isFrozen(roboticsCatalog.entries)).toBe(true);
    expect(Object.isFrozen(roboticsEntry)).toBe(true);
    expect(Object.isFrozen(roboticsEntry.lessonContent)).toBe(true);
    expect(Object.isFrozen(PHASE5_SESSIONS)).toBe(true);
    expect(Object.isFrozen(roboticsSession)).toBe(true);

    expect(() => {
      (PHASE5_COURSE_CATALOGS as CourseCatalog[]).push(roboticsCatalog);
    }).toThrow(TypeError);

    expect(() => {
      (roboticsCatalog as { courseName: string }).courseName = "Mutated";
    }).toThrow(TypeError);

    expect(() => {
      (roboticsCatalog.entries as typeof roboticsCatalog.entries & { 0: typeof roboticsEntry })[0] = {
        ...roboticsEntry,
        sessionNumber: 99,
      };
    }).toThrow(TypeError);

    expect(() => {
      (roboticsEntry as { lessonTitle: string }).lessonTitle = "Mutated";
    }).toThrow(TypeError);

    expect(() => {
      (roboticsEntry.lessonContent as string[]).push("Mutated");
    }).toThrow(TypeError);

    expect(() => {
      (PHASE5_SESSIONS as SyntheticSession[]).push(roboticsSession);
    }).toThrow(TypeError);

    expect(() => {
      (roboticsSession as { workflowStatus: SyntheticSession["workflowStatus"] }).workflowStatus =
        "context_ready";
    }).toThrow(TypeError);
  });
});
