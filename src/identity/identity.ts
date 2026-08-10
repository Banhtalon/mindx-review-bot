export type StudentCandidate = {
  lmsStudentId?: string;
  fullName: string;
  stableDiscriminator?: string;
};

export type StudentIdentityQuery = {
  lmsStudentId?: string;
  stableDiscriminator?: string;
  fullName: string;
};

function normalizeIdentityText(value: string): string {
  return value.normalize("NFC").replace(/\s+/g, " ").trim().toLocaleLowerCase();
}

export function resolveStudentIdentity(
  candidates: StudentCandidate[],
  query: StudentIdentityQuery,
): StudentCandidate {
  if (query.lmsStudentId) {
    const matches = candidates.filter(
      (candidate) => candidate.lmsStudentId === query.lmsStudentId,
    );
    if (matches.length === 1) return matches[0];
    throw new Error("Student identity is unresolvable");
  }

  if (query.stableDiscriminator) {
    const matches = candidates.filter(
      (candidate) => candidate.stableDiscriminator === query.stableDiscriminator,
    );
    if (matches.length === 1) return matches[0];
    throw new Error("Student identity is unresolvable");
  }

  const matches = candidates.filter(
    (candidate) => normalizeIdentityText(candidate.fullName) === normalizeIdentityText(query.fullName),
  );
  if (matches.length === 1 && (matches[0].lmsStudentId || matches[0].stableDiscriminator)) {
    return matches[0];
  }
  throw new Error("Student identity is unresolvable");
}
