export type AttendanceValue = "present" | "online" | "absent" | "unknown";

export type LmsContext = {
  classCode: string;
  sessionNumber: number;
  scheduledDate: string;
  startTime: string;
  endTime: string;
};

export type ContextReasonCode =
  | "LMS_CONTEXT_MATCH"
  | "LMS_CLASS_MISMATCH"
  | "LMS_SESSION_MISMATCH"
  | "LMS_DATE_MISMATCH"
  | "LMS_TIME_MISMATCH";

export type ContextAssertion = {
  matched: boolean;
  reasonCode: ContextReasonCode;
  manualFallback: boolean;
};

export type MappingStatus = "resolved" | "unresolvable" | "ambiguous";

export type LmsRosterRow = {
  rowKey: string;
  fullName: string;
  attendance: AttendanceValue;
  identityStatus: MappingStatus;
  studentId?: string;
  discriminator?: string;
};

function normalizeClassCode(value: string): string {
  return value.normalize("NFC").replace(/\s+/g, " ").trim().toLocaleUpperCase();
}

function normalizeExactValue(value: string): string {
  return value.normalize("NFC").trim();
}

function mismatch(reasonCode: Exclude<ContextReasonCode, "LMS_CONTEXT_MATCH">): ContextAssertion {
  return { matched: false, reasonCode, manualFallback: true };
}

export function assertLmsContext(expected: LmsContext, observed: LmsContext): ContextAssertion {
  if (normalizeClassCode(expected.classCode) !== normalizeClassCode(observed.classCode)) {
    return mismatch("LMS_CLASS_MISMATCH");
  }
  if (expected.sessionNumber !== observed.sessionNumber) {
    return mismatch("LMS_SESSION_MISMATCH");
  }
  if (normalizeExactValue(expected.scheduledDate) !== normalizeExactValue(observed.scheduledDate)) {
    return mismatch("LMS_DATE_MISMATCH");
  }
  if (
    normalizeExactValue(expected.startTime) !== normalizeExactValue(observed.startTime) ||
    normalizeExactValue(expected.endTime) !== normalizeExactValue(observed.endTime)
  ) {
    return mismatch("LMS_TIME_MISMATCH");
  }
  return { matched: true, reasonCode: "LMS_CONTEXT_MATCH", manualFallback: false };
}

export function getMappingStatus(
  row: LmsRosterRow,
  assignments: Readonly<Record<string, string>>,
): MappingStatus {
  return assignments[row.rowKey] ? "resolved" : row.identityStatus;
}

export function assignStudent(
  assignments: Readonly<Record<string, string>>,
  rowKey: string,
  internalId: string,
  allowedIds: ReadonlySet<string>,
): Record<string, string> {
  if (!rowKey.trim()) {
    throw new Error("Roster row key is required");
  }
  if (!allowedIds.has(internalId)) {
    throw new Error("Internal student is not an allowed mapping target");
  }
  const assignedElsewhere = Object.entries(assignments).some(
    ([existingRowKey, existingInternalId]) =>
      existingRowKey !== rowKey && existingInternalId === internalId,
  );
  if (assignedElsewhere) {
    throw new Error("Internal student is already assigned to another row");
  }
  return { ...assignments, [rowKey]: internalId };
}

export function canContinueReview(
  assertion: ContextAssertion,
  rows: ReadonlyArray<MappingStatus>,
): boolean {
  return assertion.matched && !assertion.manualFallback && rows.every((status) => status === "resolved");
}
