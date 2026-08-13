// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import App from "./App";

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
});
