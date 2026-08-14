import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import type { AuthGateway, AuthSession, WorkspaceRole } from "./contracts";

function mapSession(session: { user: { id: string; email?: string | null } } | null): AuthSession | null {
  if (!session) return null;

  return {
    user: {
      id: session.user.id,
      email: session.user.email ?? null,
    },
  };
}

function isWorkspaceRole(role: unknown): role is WorkspaceRole {
  return role === "owner" || role === "reviewer";
}

export class SupabaseAuthGateway implements AuthGateway {
  constructor(private readonly client: SupabaseClient) {}

  async getSession(): Promise<AuthSession | null> {
    const { data, error } = await this.client.auth.getSession();
    if (error) throw new Error("AUTH_SESSION_UNAVAILABLE");
    return mapSession(data.session);
  }

  async signIn(email: string, password: string): Promise<AuthSession> {
    const { data, error } = await this.client.auth.signInWithPassword({ email, password });
    const session = mapSession(data.session);
    if (error || !session) throw new Error("AUTH_SIGN_IN_FAILED");
    return session;
  }

  async signOut(): Promise<void> {
    const { error } = await this.client.auth.signOut();
    if (error) throw new Error("AUTH_SIGN_OUT_FAILED");
  }

  subscribe(listener: (session: AuthSession | null) => void): () => void {
    const { data } = this.client.auth.onAuthStateChange((_event, session) => {
      listener(mapSession(session));
    });
    return () => data.subscription.unsubscribe();
  }

  async getWorkspaceRole(workspaceId: string, userId: string): Promise<WorkspaceRole | null> {
    const { data, error } = await this.client
      .from("workspace_members")
      .select("role")
      .eq("workspace_id", workspaceId)
      .eq("user_id", userId)
      .maybeSingle();

    if (error) throw new Error("WORKSPACE_ROLE_UNAVAILABLE");
    return isWorkspaceRole(data?.role) ? data.role : null;
  }
}

export function createSupabaseAuthGateway(url: string, publishableKey: string): AuthGateway {
  return new SupabaseAuthGateway(createClient(url, publishableKey, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: false,
    },
  }));
}
