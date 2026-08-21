export type WorkspaceRole = "owner" | "reviewer";

export type AuthSession = {
  readonly user: {
    readonly id: string;
    readonly email: string | null;
  };
};

export interface AuthGateway {
  getSession(): Promise<AuthSession | null>;
  signIn(email: string, password: string): Promise<AuthSession>;
  signOut(): Promise<void>;
  subscribe(listener: (session: AuthSession | null) => void): () => void;
  getWorkspaceRole(workspaceId: string, userId: string): Promise<WorkspaceRole | null>;
}
