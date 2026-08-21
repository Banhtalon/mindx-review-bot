export type AuthRuntimeConfigInput = {
  readonly url?: string;
  readonly publishableKey?: string;
  readonly workspaceId?: string;
};

export type AuthRuntimeConfig =
  | { readonly mode: "synthetic" }
  | {
      readonly mode: "authenticated";
      readonly url: string;
      readonly publishableKey: string;
      readonly workspaceId: string;
    }
  | { readonly mode: "invalid"; readonly reason: "INCOMPLETE_AUTH_CONFIG" };

function trim(value: string | undefined): string {
  return value?.trim() ?? "";
}

export function resolveAuthRuntimeConfig(input: AuthRuntimeConfigInput): AuthRuntimeConfig {
  const url = trim(input.url);
  const publishableKey = trim(input.publishableKey);
  const workspaceId = trim(input.workspaceId);
  const configured = [url, publishableKey, workspaceId].filter(Boolean).length;

  if (configured === 0) return { mode: "synthetic" };
  if (configured !== 3) return { mode: "invalid", reason: "INCOMPLETE_AUTH_CONFIG" };

  return {
    mode: "authenticated",
    url,
    publishableKey,
    workspaceId,
  };
}
