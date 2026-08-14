// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App, { Phase5BReviewInputSurface, Phase5ContextSurface } from "./App";
import type { CourseCatalog, SyntheticSession } from "./curriculum/contracts";
import {
  createInitialReviewInputs,
  PHASE5B_SYNTHETIC_LEARNERS,
} from "./fixtures/phase5bReviewInputs";
import { InMemorySyntheticReviewDraftStore } from "./reviewInputs/syntheticDraftStore";

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

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  cleanup();
});

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

describe("Synthetic review inputs", () => {
  const createDraftStore = () =>
    new InMemorySyntheticReviewDraftStore(
      "synthetic-robotics-session-3",
      createInitialReviewInputs(PHASE5B_SYNTHETIC_LEARNERS),
    );

  it("commits the latest synthetic edit only after 300 milliseconds", () => {
    vi.useFakeTimers();
    const store = createDraftStore();
    render(<Phase5BReviewInputSurface store={store} />);

    fireEvent.change(
      screen.getByRole("textbox", { name: "Synthetic learner 01 draft note" }),
      { target: { value: "Local synthetic autosave note" } },
    );

    expect(screen.getByText("Draft pending")).toBeVisible();
    expect(store.read().revision).toBe(1);

    act(() => vi.advanceTimersByTime(299));
    expect(store.read().revision).toBe(1);

    act(() => vi.advanceTimersByTime(1));
    expect(store.read().revision).toBe(2);
    expect(store.read().inputs[0].noteDraft).toBe("Local synthetic autosave note");
    expect(screen.getByText("Saved locally · revision 2")).toBeVisible();
  });

  it("commits incomplete attendance without opening the generation gate", () => {
    vi.useFakeTimers();
    const store = createDraftStore();
    render(<Phase5BReviewInputSurface store={store} />);

    fireEvent.change(
      screen.getByRole("combobox", { name: "Synthetic learner 01 level" }),
      { target: { value: "developing" } },
    );
    act(() => vi.advanceTimersByTime(300));

    expect(store.read().revision).toBe(2);
    expect(screen.getByText("Generation blocked: attendance unknown")).toBeVisible();
    expect(screen.getByText("Saved locally · revision 2")).toBeVisible();
  });

  it("does not issue a network request while committing a synthetic draft", () => {
    vi.useFakeTimers();
    const requestSpy = vi.fn();
    vi.stubGlobal("fetch", requestSpy);
    const store = createDraftStore();
    render(<Phase5BReviewInputSurface store={store} />);

    fireEvent.change(
      screen.getByRole("textbox", { name: "Synthetic learner 02 draft note" }),
      { target: { value: "Synthetic local-only note" } },
    );
    act(() => vi.advanceTimersByTime(300));

    expect(requestSpy).not.toHaveBeenCalled();
    expect(store.read().revision).toBe(2);
  });

  it("starts blocked with three local synthetic learner drafts and no write actions", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "Synthetic review inputs" })).toBeVisible();
    expect(screen.getByText("Generation blocked: attendance unknown")).toBeVisible();
    expect(screen.getByRole("button", { name: "Mark all present" })).toBeEnabled();
    expect(screen.getAllByRole("combobox", { name: / attendance$/i })).toHaveLength(3);
    const blockedActionLabels = [
      ["s", "a", "v", "e"].join(""),
      ["s", "u", "b", "m", "i", "t"].join(""),
      ["g", "e", "n", "e", "r", "a", "t", "e"].join(""),
    ];
    const blockedActionPattern = new RegExp(blockedActionLabels.join("|"), "i");
    const buttonLabels = screen
      .getAllByRole("button")
      .map((button) => button.textContent?.trim().toLowerCase());

    expect(buttonLabels.some((label) => blockedActionPattern.test(label ?? ""))).toBe(false);
  });

  it("marks every learner present without requiring levels or notes", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Mark all present" }));

    screen
      .getAllByRole("combobox", { name: / attendance$/i })
      .forEach((control) => expect(control).toHaveValue("present"));
    expect(screen.getByText("Generation ready: attendance complete")).toBeVisible();
    expect(screen.getByRole("combobox", { name: "Synthetic learner 01 level" })).toHaveValue("unknown");
    expect(screen.getByRole("textbox", { name: "Synthetic learner 01 draft note" })).toHaveValue("");
  });

  it("allows absent attendance but blocks again when a row returns to unknown", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Mark all present" }));
    fireEvent.change(screen.getByRole("combobox", { name: "Synthetic learner 02 attendance" }), {
      target: { value: "absent" },
    });

    expect(screen.getByText("Generation ready: attendance complete")).toBeVisible();

    fireEvent.change(screen.getByRole("combobox", { name: "Synthetic learner 02 attendance" }), {
      target: { value: "unknown" },
    });

    expect(screen.getByText("Generation blocked: attendance unknown")).toBeVisible();
    expect(screen.getByText(/Reason code: ATTENDANCE_UNKNOWN/)).toBeVisible();
  });

  it("keeps learning level and note edits local without changing attendance readiness", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "Mark all present" }));
    fireEvent.change(screen.getByRole("combobox", { name: "Synthetic learner 01 level" }), {
      target: { value: "developing" },
    });
    fireEvent.change(screen.getByRole("textbox", { name: "Synthetic learner 01 draft note" }), {
      target: { value: "Needs more practice with the synthetic exercise." },
    });

    expect(screen.getByRole("combobox", { name: "Synthetic learner 01 level" })).toHaveValue("developing");
    expect(screen.getByRole("textbox", { name: "Synthetic learner 01 draft note" })).toHaveValue(
      "Needs more practice with the synthetic exercise.",
    );
    expect(screen.getByText("Generation ready: attendance complete")).toBeVisible();
  });
});
