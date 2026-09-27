import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { AuthBoundary } from "./auth/AuthBoundary";
import { resolveAuthRuntimeConfig } from "./auth/runtimeConfig";
import { createSupabaseAuthGateway } from "./auth/supabaseAuthGateway";
import "./styles.css";
import { SafeErrorBoundary } from "./ui/SafeErrorBoundary";

const authRuntimeConfig = resolveAuthRuntimeConfig({
  url: import.meta.env.VITE_SUPABASE_URL,
  publishableKey: import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY,
  workspaceId: import.meta.env.VITE_SUPABASE_WORKSPACE_ID,
});
const authGateway = authRuntimeConfig.mode === "authenticated"
  ? createSupabaseAuthGateway(authRuntimeConfig.url, authRuntimeConfig.publishableKey)
  : null;

function ApplicationShell() {
  if (authRuntimeConfig.mode === "synthetic") {
    if (import.meta.env.DEV) return <App />;
    return (
      <main>
        <h1>Configuration unavailable</h1>
        <p role="alert">
          Dữ liệu synthetic chỉ được phép chạy ở môi trường phát triển. Hãy cấu hình Supabase trước khi triển khai.
        </p>
      </main>
    );
  }

  if (authRuntimeConfig.mode === "invalid") {
    return (
      <main>
        <h1>Configuration unavailable</h1>
        <p role="alert">Authentication is unavailable because the required configuration is incomplete.</p>
      </main>
    );
  }

  if (authGateway === null) {
    return (
      <main>
        <h1>Configuration unavailable</h1>
        <p role="alert">Authentication is unavailable because the required configuration is incomplete.</p>
      </main>
    );
  }

  return (
    <AuthBoundary gateway={authGateway} workspaceId={authRuntimeConfig.workspaceId}>
      <App mode="hosted" workspaceId={authRuntimeConfig.workspaceId} />
    </AuthBoundary>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <SafeErrorBoundary>
      <ApplicationShell />
    </SafeErrorBoundary>
  </StrictMode>,
);
