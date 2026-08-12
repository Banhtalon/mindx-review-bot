import type { DispatchAdapterConfig } from "./edgeAdapters.ts";

export type EnvironmentReader = {
  get(name: string): string | undefined;
};

export type DispatchEnvironment = DispatchAdapterConfig & {
  cronSecret: string;
  cronActorUserId: string;
  cronWorkspaceId: string;
};

function misconfigured(): never {
  throw new Error("DISPATCH_FUNCTION_MISCONFIGURED");
}

function requiredEnvironment(
  environment: EnvironmentReader,
  name: string,
): string {
  const value = environment.get(name);
  if (value === undefined || value.length === 0) misconfigured();
  return value;
}

function hostedDefaultKey(
  environment: EnvironmentReader,
  name: string,
): string | undefined {
  const rawValue = environment.get(name);
  if (rawValue === undefined) return undefined;

  let parsed: unknown;
  try {
    parsed = JSON.parse(rawValue);
  } catch {
    misconfigured();
  }

  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    misconfigured();
  }
  const value = (parsed as Record<string, unknown>).default;
  if (typeof value !== "string" || value.length === 0) misconfigured();
  return value;
}

function apiKey(
  environment: EnvironmentReader,
  hostedName: string,
  localName: string,
): string {
  return hostedDefaultKey(environment, hostedName)
    ?? requiredEnvironment(environment, localName);
}

export function loadDispatchEnvironment(
  environment: EnvironmentReader,
): DispatchEnvironment {
  const githubRepository = requiredEnvironment(environment, "GITHUB_REPOSITORY");
  const githubWorkflowId = requiredEnvironment(environment, "GITHUB_WORKFLOW_ID");
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(githubRepository)) {
    misconfigured();
  }
  if (!/^[A-Za-z0-9_.-]+$/.test(githubWorkflowId)) misconfigured();

  return {
    supabaseUrl: requiredEnvironment(environment, "SUPABASE_URL").replace(/\/$/, ""),
    publishableKey: apiKey(
      environment,
      "SUPABASE_PUBLISHABLE_KEYS",
      "SUPABASE_PUBLISHABLE_KEY",
    ),
    serviceKey: apiKey(
      environment,
      "SUPABASE_SECRET_KEYS",
      "SUPABASE_SECRET_KEY",
    ),
    githubToken: requiredEnvironment(environment, "GITHUB_DISPATCH_TOKEN"),
    githubRepository,
    githubWorkflowId,
    githubRef: environment.get("GITHUB_REF") || "main",
    cronSecret: requiredEnvironment(environment, "CRON_DISPATCH_SECRET"),
    cronActorUserId: requiredEnvironment(environment, "CRON_ACTOR_USER_ID"),
    cronWorkspaceId: requiredEnvironment(environment, "CRON_WORKSPACE_ID"),
  };
}
