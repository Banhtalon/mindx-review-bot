export type AutomationConfig = {
  automationEnabled: boolean;
};

export type LmsWriteConfig = {
  lmsWriteEnabled: boolean;
};

export type DomainMode = "production" | "synthetic";

const PRODUCTION_HOSTS = new Set(["teachingmindx.top", "lms.mindx.edu.vn"]);
const SYNTHETIC_HOSTS = new Set(["127.0.0.1", "localhost"]);

export function canRunAutomation(config: AutomationConfig): boolean {
  return config.automationEnabled === true;
}

export function assertLmsReadOnly(config: LmsWriteConfig): void {
  if (config.lmsWriteEnabled !== false) {
    throw new Error("LMS read-only guard violated");
  }
}

export function assertAllowedDomain(url: string, mode: DomainMode = "production"): void {
  const parsed = new URL(url);
  const allowedHosts = mode === "synthetic"
    ? new Set([...PRODUCTION_HOSTS, ...SYNTHETIC_HOSTS])
    : PRODUCTION_HOSTS;
  const validProtocol = mode === "synthetic"
    ? parsed.protocol === "http:" || parsed.protocol === "https:"
    : parsed.protocol === "https:";

  if (!validProtocol || !allowedHosts.has(parsed.hostname)) {
    throw new Error("Domain is not allowlisted");
  }
}
