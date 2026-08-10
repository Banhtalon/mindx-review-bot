// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("Bootstrap shell", () => {
  it("identifies the synthetic-only Spike 0 mode", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "MindX Review Bot" })).toBeVisible();
    expect(screen.getByText("Synthetic-ready Spike 0")).toBeVisible();
    expect(screen.getByText("LMS write actions disabled")).toBeVisible();
  });
});
