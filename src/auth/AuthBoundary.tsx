import { useEffect, useState, type ReactNode } from "react";
import type { AuthGateway, AuthSession, WorkspaceRole } from "./contracts";

type AuthBoundaryProps = {
  readonly gateway: AuthGateway;
  readonly workspaceId: string;
  readonly children: ReactNode;
};

function roleLabel(role: WorkspaceRole): string {
  return role === "owner" ? "Owner" : "Reviewer";
}

export function AuthBoundary({ gateway, workspaceId, children }: AuthBoundaryProps) {
  const [session, setSession] = useState<AuthSession | null | undefined>(undefined);
  const [role, setRole] = useState<WorkspaceRole | null | undefined>(undefined);
  const [signInError, setSignInError] = useState(false);
  const [isSigningIn, setIsSigningIn] = useState(false);

  useEffect(() => {
    let active = true;

    const resolveSession = async (nextSession: AuthSession | null) => {
      if (!active) return;
      setSession(nextSession);
      setSignInError(false);

      if (!nextSession) {
        setRole(undefined);
        return;
      }

      setRole(undefined);
      try {
        const nextRole = await gateway.getWorkspaceRole(workspaceId, nextSession.user.id);
        if (active) setRole(nextRole);
      } catch {
        if (active) setRole(null);
      }
    };

    void gateway.getSession().then(resolveSession).catch(() => resolveSession(null));
    const unsubscribe = gateway.subscribe((nextSession) => void resolveSession(nextSession));

    return () => {
      active = false;
      unsubscribe();
    };
  }, [gateway, workspaceId]);

  const signIn = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "");
    const password = String(form.get("password") ?? "");
    setIsSigningIn(true);
    setSignInError(false);

    try {
      const nextSession = await gateway.signIn(email, password);
      setSession(nextSession);
      try {
        setRole(await gateway.getWorkspaceRole(workspaceId, nextSession.user.id));
      } catch {
        setRole(null);
      }
    } catch {
      setSignInError(true);
    } finally {
      setIsSigningIn(false);
    }
  };

  const signOut = async () => {
    try {
      await gateway.signOut();
      setSession(null);
      setRole(undefined);
    } catch {
      setSignInError(true);
    }
  };

  if (session === undefined) {
    return <p role="status">Checking your session…</p>;
  }

  if (!session) {
    return (
      <main>
        <h1>Sign in</h1>
        <form onSubmit={signIn}>
          <label>
            Email
            <input name="email" type="email" autoComplete="email" required />
          </label>
          <label>
            Password
            <input name="password" type="password" autoComplete="current-password" required />
          </label>
          {signInError && <p role="alert">Unable to sign in safely. Check your details and try again.</p>}
          <button type="submit" disabled={isSigningIn}>{isSigningIn ? "Signing in…" : "Sign in"}</button>
        </form>
      </main>
    );
  }

  if (role === undefined) {
    return <p role="status">Checking workspace access…</p>;
  }

  if (!role) {
    return (
      <main>
        <h1>Access denied</h1>
        <p>You do not have access to this workspace.</p>
        <button type="button" onClick={() => void signOut()}>Log out</button>
      </main>
    );
  }

  return (
    <>
      <header>
        <span>Role: {roleLabel(role)}</span>
        <button type="button" onClick={() => void signOut()}>Log out</button>
      </header>
      {children}
    </>
  );
}
