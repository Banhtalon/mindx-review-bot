import {
  handleDispatch,
  type DispatchConfig,
  type DispatchDependencies,
  type DispatchRequest,
} from "./dispatch";

function jsonResponse(body: unknown, status: number): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Cache-Control": "no-store",
      "Content-Type": "application/json",
    },
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function safeErrorCode(error: unknown): string {
  if (typeof error === "object" && error !== null && "code" in error) {
    const code = error.code;
    if (typeof code === "string" && /^[A-Z][A-Z0-9_]{2,63}$/.test(code)) return code;
  }
  return "SUPABASE_UNAVAILABLE";
}

async function parseRequest(request: Request): Promise<DispatchRequest> {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    throw new Error("INVALID_JSON");
  }
  if (!isRecord(body)) throw new Error("INVALID_REQUEST");
  if (
    typeof body.workspace_id !== "string" ||
    typeof body.type !== "string" ||
    typeof body.idempotency_key !== "string"
  ) {
    throw new Error("INVALID_REQUEST");
  }
  return {
    authorization: request.headers.get("authorization") ?? undefined,
    cronSecret: request.headers.get("x-cron-dispatch-secret") ?? undefined,
    workspaceId: body.workspace_id,
    type: body.type,
    idempotencyKey: body.idempotency_key,
    payload: "payload" in body ? body.payload : {},
  };
}

export function createDispatchHttpHandler(
  dependencies: DispatchDependencies,
  config: DispatchConfig,
): (request: Request) => Promise<Response> {
  return async (request) => {
    if (request.method !== "POST") {
      return jsonResponse({ error_code: "METHOD_NOT_ALLOWED" }, 405);
    }

    let command: DispatchRequest;
    try {
      command = await parseRequest(request);
    } catch (error) {
      const code = error instanceof Error && error.message === "INVALID_JSON"
        ? "INVALID_JSON"
        : "INVALID_REQUEST";
      return jsonResponse({ error_code: code }, 400);
    }

    try {
      const result = await handleDispatch(command, dependencies, config);
      return jsonResponse(result.body, result.status);
    } catch (error) {
      return jsonResponse({ error_code: safeErrorCode(error) }, 500);
    }
  };
}
