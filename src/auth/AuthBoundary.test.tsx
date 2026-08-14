// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { AuthBoundary } from "./AuthBoundary";
import type { AuthGateway, AuthSession, WorkspaceRole } from "./contracts";

const WORKSPACE_ID = "00000000-0000-0000-0000-0000000000a1";

class FakeAuthGateway implements AuthGateway {
  private listeners = new Set<(session: AuthSession | null) => void>();

  constructor(
    private session: AuthSession | null,
    private readonly role: WorkspaceRole | null,
  ) {}

  async getSession(): Promise<AuthSession | null> {
    return this.session;
  }

  async signIn(email: string, password: string): Promise<AuthSession> {
    void password;
    this.session = { user: { id: "synthetic-user", email } };
    this.notify();
    return this.session;
  }

  async signOut(): Promise<void> {
    this.session = null;
    this.notify();
  }

  subscribe(listener: (session: AuthSession | null) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  async getWorkspaceRole(workspaceId: string, userId: string): Promise<WorkspaceRole | null> {
    void workspaceId;
    void userId;
    return this.role;
  }

  private notify(): void {
    for (const listener of this.listeners) listener(this.session);
  }
}

function protectedSurface(gateway: AuthGateway) {
  return render(
    <AuthBoundary gateway={gateway} workspaceId={WORKSPACE_ID}>
      <p>Protected synthetic dashboard</p>
    </AuthBoundary>,
  );
}

afterEach(cleanup);

describe("AuthBoundary", () => {
  it("shows a sign-in form when no session exists", async () => {
    protectedSurface(new FakeAuthGateway(null, "owner"));

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeVisible();
    expect(screen.getByLabelText("Email")).toBeVisible();
    expect(screen.queryByText("Protected synthetic dashboard")).not.toBeInTheDocument();
  });

  it("shows protected content and removes it again after logout", async () => {
    protectedSurface(new FakeAuthGateway(null, "owner"));

    fireEvent.change(await screen.findByLabelText("Email"), {
      target: { value: "owner@example.invalid" },
    });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "synthetic-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Protected synthetic dashboard")).toBeVisible();
    expect(screen.getByText("Role: Owner")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Log out" }));

    await waitFor(() => {
      expect(screen.queryByText("Protected synthetic dashboard")).not.toBeInTheDocument();
    });
    expect(screen.getByRole("heading", { name: "Sign in" })).toBeVisible();
  });

  it.each([
    ["owner", "Role: Owner"],
    ["reviewer", "Role: Reviewer"],
  ] as const)("labels the %s workspace role distinctly", async (role, expectedLabel) => {
    protectedSurface(new FakeAuthGateway({ user: { id: "synthetic-user", email: "user@example.invalid" } }, role));

    expect(await screen.findByText("Protected synthetic dashboard")).toBeVisible();
    expect(screen.getByText(expectedLabel)).toBeVisible();
  });

  it("denies access when the signed-in user has no workspace membership", async () => {
    protectedSurface(new FakeAuthGateway({ user: { id: "synthetic-user", email: "user@example.invalid" } }, null));

    expect(await screen.findByRole("heading", { name: "Access denied" })).toBeVisible();
    expect(screen.queryByText("Protected synthetic dashboard")).not.toBeInTheDocument();
  });
});
