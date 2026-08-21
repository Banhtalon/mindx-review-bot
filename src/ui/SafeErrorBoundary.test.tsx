// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SafeErrorBoundary } from "./SafeErrorBoundary";

function ThrowingChild(): ReactNode {
  throw new Error("Synthetic exception details must stay private");
}

function callContains(calls: unknown[][], value: string): boolean {
  return calls.some((call) => call.some((argument) => String(argument).includes(value)));
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("SafeErrorBoundary", () => {
  it("does not send raw exception details to application-controlled console logging", () => {
    const rawDetail = "Synthetic exception details must stay private";
    const consoleError = vi.spyOn(console, "error");
    const boundary = new SafeErrorBoundary({ children: null });

    boundary.componentDidCatch(new Error(rawDetail));

    expect(callContains(consoleError.mock.calls, rawDetail)).toBe(false);
  });

  it("shows a stable safe message without rendering exception details", () => {
    // React may emit its own development diagnostic for a thrown child. That framework output
    // is not application-controlled; the lifecycle test above covers this boundary's logging.

    render(
      <SafeErrorBoundary>
        <ThrowingChild />
      </SafeErrorBoundary>,
    );

    expect(screen.getByText("The application could not continue safely. Reload the page to try again.")).toBeVisible();
    expect(screen.queryByText("Synthetic exception details must stay private")).not.toBeInTheDocument();
  });
});
