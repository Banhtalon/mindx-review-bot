export type CronDispatchEnvironment = Readonly<Record<string, string | undefined>>;

export type CronDispatchInput = {
  readonly SUPABASE_URL?: string;
  readonly CRON_DISPATCH_SECRET?: string;
  readonly CRON_WORKSPACE_ID?: string;
  readonly JOB_TYPE?: string;
  readonly now?: Date;
};

export type CronDispatchRequest = {
  readonly url: string;
  readonly headers: Readonly<Record<string, string>>;
  readonly body: string;
};

export class CronDispatchError extends Error {
  readonly code: string;
}

export function buildCronDispatchRequest(input: CronDispatchInput): CronDispatchRequest;

export function dispatchCronJob(options?: {
  readonly environment?: CronDispatchEnvironment;
  readonly fetcher?: typeof fetch;
  readonly now?: Date;
}): Promise<{ jobId: string; status: string }>;
