# Supabase Edge key environment compatibility

## Goal

Make the `dispatch-job` Edge Function load Supabase's hosted API keys without attempting to create reserved `SUPABASE_*` custom secrets, while preserving local development compatibility.

## Design

The Edge Function will move environment parsing into a small shared, pure module. It will read `SUPABASE_URL` from the platform environment, then resolve the `default` entry from the hosted JSON variables `SUPABASE_PUBLISHABLE_KEYS` and `SUPABASE_SECRET_KEYS`. For local `supabase functions serve` environments, it will fall back to the existing singular variables `SUPABASE_PUBLISHABLE_KEY` and `SUPABASE_SECRET_KEY`.

Malformed JSON, missing objects, missing `default` entries, and empty values will all fail closed with the existing `DISPATCH_FUNCTION_MISCONFIGURED` error. No secret values will be logged or included in errors.

## Scope

- Modify only Edge Function environment parsing and its tests.
- Keep GitHub dispatch, RLS, cron authentication, and read-only MVP behavior unchanged.
- Do not create or commit real secret files.
- Update `.env.example` comments/names only if needed to distinguish hosted built-ins from local fallback variables.

## Verification

- Test hosted JSON key resolution.
- Test local singular fallback.
- Test malformed/missing `default` configuration.
- Run lint, typecheck, unit tests, build, no-secret check, no-live-write check, and RLS tests.
