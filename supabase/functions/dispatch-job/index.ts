/* global Deno */

import { createDispatchDependencies, type DispatchAdapterConfig } from "../_shared/edgeAdapters.ts";
import { createDispatchHttpHandler } from "../_shared/http.ts";

function requiredEnvironment(name: string): string {
  const value = Deno.env.get(name);
  if (value === undefined || value.length === 0) {
    throw new Error("DISPATCH_FUNCTION_MISCONFIGURED");
  }
  return value;
}

function loadAdapterConfig(): DispatchAdapterConfig {
  const githubRepository = requiredEnvironment("GITHUB_REPOSITORY");
  const githubWorkflowId = requiredEnvironment("GITHUB_WORKFLOW_ID");
  if (!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(githubRepository)) {
    throw new Error("DISPATCH_FUNCTION_MISCONFIGURED");
  }
  if (!/^[A-Za-z0-9_.-]+$/.test(githubWorkflowId)) {
    throw new Error("DISPATCH_FUNCTION_MISCONFIGURED");
  }
  return {
    supabaseUrl: requiredEnvironment("SUPABASE_URL").replace(/\/$/, ""),
    publishableKey: requiredEnvironment("SUPABASE_PUBLISHABLE_KEY"),
    serviceKey: requiredEnvironment("SUPABASE_SECRET_KEY"),
    githubToken: requiredEnvironment("GITHUB_DISPATCH_TOKEN"),
    githubRepository,
    githubWorkflowId,
    githubRef: Deno.env.get("GITHUB_REF") || "main",
  };
}

const adapterConfig = loadAdapterConfig();
const dispatchConfig = {
  cronSecret: requiredEnvironment("CRON_DISPATCH_SECRET"),
  cronActorUserId: requiredEnvironment("CRON_ACTOR_USER_ID"),
  cronWorkspaceId: requiredEnvironment("CRON_WORKSPACE_ID"),
};
const handler = createDispatchHttpHandler(
  createDispatchDependencies(adapterConfig),
  dispatchConfig,
);

Deno.serve(handler);
