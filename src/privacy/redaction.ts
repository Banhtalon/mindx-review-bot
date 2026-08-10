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

const SAFE_EVIDENCE_IDS = new Set([
  "V4-S0-01",
  "V4-S0-02",
  "V4-S0-03",
  "V4-S0-04",
  "V4-S0-05",
  "V4-S0-06",
  "V4-S0-07",
  "V4-S0-08",
  "V4-S0-09",
  "V4-S0-10",
  "V4-S0-11",
  "V4-S0-07-fixture",
  "V4-S0-10-fixture",
]);
const RESIDUAL_PERSONAL_MARKERS = [
  /(?:\b(?:student|parent)\s+[A-Z][A-Za-zÀ-ỹ'-]+|\b(?:học viên|phụ huynh)\s+[A-ZÀ-Ỹ][\p{L}'-]+|@|\b(?:\+?84|0)\d{8,10}\b)/iu,
  /(?<![\p{L}'])\p{Lu}[\p{L}'-]{2,}(?:\s+\p{Lu}[\p{L}'-]{2,})+(?![\p{L}'])/u,
];

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

  output = output
    .replace(/[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}/g, "[REDACTED]")
    .replace(/\b(?:\+?84|0)\d{8,10}\b/g, "[REDACTED]");
  if (RESIDUAL_PERSONAL_MARKERS.some((pattern) => pattern.test(output))) {
    throw new Error("Performance text contains unredacted personal data");
  }
  return output;
}

function assertSafeEvidenceId(evidenceId: string): void {
  if (!SAFE_EVIDENCE_IDS.has(evidenceId)) {
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
