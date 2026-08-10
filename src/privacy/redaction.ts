export type ModelInput = {
  studentName: string;
  parentName: string;
  email: string;
  phone: string;
  address: string;
  healthNote: string;
  performance: string;
  evidenceId: string;
};

export type SafeModelPayload = {
  anonymousId: string;
  performance: string;
  evidenceId: string;
};

const SAFE_EVIDENCE_ID = /^V4-[A-Z0-9]+-\d{2}(?:-[a-z0-9]+)*$/;

function anonymousId(): string {
  const values = new Uint32Array(3);
  globalThis.crypto.getRandomValues(values);
  const token = Array.from(values, (value) => value.toString(36).toUpperCase())
    .join("")
    .replace(/[^A-Z0-9]/g, "")
    .slice(0, 6)
    .padEnd(6, "0");
  return `SYN-${token}`;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function redactPerformance(input: ModelInput): string {
  let output = input.performance;
  for (const sensitiveValue of [
    input.studentName,
    input.parentName,
    input.email,
    input.phone,
    input.address,
    input.healthNote,
  ]) {
    if (sensitiveValue.trim()) {
      output = output.replace(
        new RegExp(escapeRegExp(sensitiveValue), "gi"),
        "[REDACTED]",
      );
    }
  }

  return output
    .replace(/[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/g, "[REDACTED_EMAIL]")
    .replace(/\b(?:\+?84|0)\d{8,10}\b/g, "[REDACTED_PHONE]");
}

function assertSafeEvidenceId(evidenceId: string): void {
  if (!SAFE_EVIDENCE_ID.test(evidenceId)) {
    throw new Error("Evidence ID is not safe");
  }
}

export function buildSafeModelPayload(input: ModelInput): SafeModelPayload {
  assertSafeEvidenceId(input.evidenceId);
  return {
    anonymousId: anonymousId(),
    performance: redactPerformance(input),
    evidenceId: input.evidenceId,
  };
}
