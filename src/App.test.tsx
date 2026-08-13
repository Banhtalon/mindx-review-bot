// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import App, { Phase5ContextSurface } from "./App";
import type { CourseCatalog, SyntheticSession } from "./curriculum/contracts";

const MANUAL_FALLBACK_CATALOGS = [
  {
    courseCode: "SYN-MANUAL-FOUNDATION",
    courseName: "Synthetic Manual Foundation",
    totalSessions: 3,
    entries: [
      {
        sessionNumber: 1,
        lessonTitle: "Synthetic manual context",
        lessonContent: ["Review synthetic manual context"],
      },
    ],
  },
] as const satisfies readonly CourseCatalog[];

const MANUAL_FALLBACK_SESSIONS = [
  {
    id: "synthetic-manual-session-1",
    classCode: "SYN-MANUAL-01",
    courseCode: "SYN-MANUAL-FOUNDATION",
    sessionNumber: 1,
    scheduledDate: "2026-09-01",
    startTime: "18:00",
    endTime: "19:30",
    workflowStatus: "context_pending",
  },
  {
    id: "synthetic-manual-session-2a",
    classCode: "SYN-MANUAL-01",
    courseCode: "SYN-MANUAL-FOUNDATION",
    sessionNumber: 2,
    scheduledDate: "2026-09-08",
    startTime: "18:00",
    endTime: "19:30",
    workflowStatus: "context_pending",
  },
  {
    id: "synthetic-manual-session-2b",
    classCode: "SYN-MANUAL-01",
    courseCode: "SYN-MANUAL-FOUNDATION",
    sessionNumber: 3,
    scheduledDate: "2026-09-08",
    startTime: "18:00",
    endTime: "19:30",
    workflowStatus: "context_pending",
  },
] as const satisfies readonly SyntheticSession[];

const NEXT_CURRICULUM_MISSING_CATALOGS = [
  {
    courseCode: "SYN-MISSING-NEXT",
    courseName: "Synthetic Missing Next Foundation",
    totalSessions: 2,
    entries: [
      {
        sessionNumber: 1,
        lessonTitle: "Synthetic current-only lesson",
        lessonContent: ["Use only the selected session curriculum"],
      },
    ],
  },
] as const satisfies readonly CourseCatalog[];

const NEXT_CURRICULUM_MISSING_SESSIONS = [
  {
    id: "synthetic-missing-next-session-1",
    classCode: "SYN-MISSING-01",
    courseCode: "SYN-MISSING-NEXT",
    sessionNumber: 1,
    scheduledDate: "2026-10-01",
    startTime: "18:00",
    endTime: "19:30",
    workflowStatus: "context_pending",
  },
  {
    id: "synthetic-missing-next-session-2",
    classCode: "SYN-MISSING-01",
    courseCode: "SYN-MISSING-NEXT",
    sessionNumber: 2,
    scheduledDate: "2026-10-08",
    startTime: "18:00",
    endTime: "19:30",
    workflowStatus: "context_pending",
  },
] as const satisfies readonly SyntheticSession[];

afterEach(() => cleanup());

describe("Bootstrap shell", () => {
  it("identifies the synthetic-only Spike 0 mode", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "MindX Review Bot" })).toBeVisible();
    expect(screen.getByText("Synthetic-ready Spike 0")).toBeVisible();
    expect(screen.getByText("LMS write actions disabled")).toBeVisible();
  });

  it("shows the manual fallback and blocks continuation for a mismatched context", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /xem trạng thái context sai/i }));

    expect(screen.getByText(/manual fallback bắt buộc/i)).toBeVisible();
    expect(screen.getByRole("button", { name: /tiếp tục khi đã giải quyết/i })).toBeDisabled();
  });

  it("requires explicit mapping before the review can continue", () => {
    render(<App />);
    const continueButton = screen.getByRole("button", { name: /tiếp tục khi đã giải quyết/i });

    expect(continueButton).toBeDisabled();

    fireEvent.change(screen.getByRole("combobox", { name: /student beta/i }), {
      target: { value: "internal-002" },
    });
    fireEvent.change(screen.getByRole("combobox", { name: /student gamma/i }), {
      target: { value: "internal-003" },
    });

    expect(continueButton).toBeEnabled();
  });

  it("shows the selected synthetic lesson and actual next session", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "Curriculum and session context" })).toBeVisible();
    expect(screen.getByText("Synthetic read-only")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Current lesson" })).toBeVisible();
    expect(screen.getByText("Robotics session three synthetic lesson")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Next actual session" })).toBeVisible();
    expect(screen.getByText(/Session 5/)).toBeVisible();
  });

  it("shows a final-session warning without inventing a next lesson", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /select SYN-ROBOTICS-01 session 5/i }));

    expect(screen.getByText("No next lesson is scheduled")).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Next actual session" })).not.toBeInTheDocument();
  });

  it("shows a missing-curriculum warning for an incomplete synthetic session", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /select SYN-PYTHON-02 session 2/i }));

    expect(screen.getByText("Curriculum unavailable")).toBeVisible();
  });

  it("requires manual review without inventing a next lesson for an ambiguous synthetic next slot", () => {
    render(
      <Phase5ContextSurface
        sessions={MANUAL_FALLBACK_SESSIONS}
        courseCatalogs={MANUAL_FALLBACK_CATALOGS}
      />,
    );

    expect(screen.getByRole("heading", { name: "Context requires manual review" })).toBeVisible();
    expect(screen.getByText("NEXT_SESSION_AMBIGUOUS")).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Next actual session" })).not.toBeInTheDocument();
  });

  it("shows a warning when the actual next session has no curriculum entry", () => {
    render(
      <Phase5ContextSurface
        sessions={NEXT_CURRICULUM_MISSING_SESSIONS}
        courseCatalogs={NEXT_CURRICULUM_MISSING_CATALOGS}
      />,
    );

    const nextSessionHeading = screen.getByRole("heading", { name: "Next actual session" });
    const nextSessionCard = nextSessionHeading.closest("article");

    expect(nextSessionCard).not.toBeNull();
    expect(nextSessionHeading).toBeVisible();
    expect(screen.getByRole("heading", { name: "Next lesson curriculum unavailable" })).toBeVisible();
    expect(screen.getByText("NEXT_CURRICULUM_MISSING")).toBeVisible();
    expect(within(nextSessionCard!).queryByText("Synthetic current-only lesson")).not.toBeInTheDocument();
  });
});
