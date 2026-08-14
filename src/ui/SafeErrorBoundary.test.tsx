// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SafeErrorBoundary } from "./SafeErrorBoundary";

function ThrowingChild(): ReactNode {
  throw new Error("Synthetic exception details must stay private");
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("SafeErrorBoundary", () => {
  it("shows a stable safe message without rendering exception details", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    render(
      <SafeErrorBoundary>
        <ThrowingChild />
      </SafeErrorBoundary>,
    );

    expect(screen.getByText("The application could not continue safely. Reload the page to try again.")).toBeVisible();
    expect(screen.queryByText("Synthetic exception details must stay private")).not.toBeInTheDocument();
  });
});
