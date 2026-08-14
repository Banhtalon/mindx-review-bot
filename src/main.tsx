import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { AuthBoundary } from "./auth/AuthBoundary";
import { createSupabaseAuthGateway } from "./auth/supabaseAuthGateway";
import "./styles.css";
import { SafeErrorBoundary } from "./ui/SafeErrorBoundary";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL?.trim();
const supabasePublishableKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY?.trim();
const supabaseWorkspaceId = import.meta.env.VITE_SUPABASE_WORKSPACE_ID?.trim();

const authGateway = supabaseUrl && supabasePublishableKey && supabaseWorkspaceId
  ? createSupabaseAuthGateway(supabaseUrl, supabasePublishableKey)
  : null;

function ApplicationShell() {
  if (!authGateway || !supabaseWorkspaceId) {
    return <App />;
  }

  return (
    <AuthBoundary gateway={authGateway} workspaceId={supabaseWorkspaceId}>
      <App />
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
