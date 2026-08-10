import { describe, expect, it } from "vitest";
import { resolveStudentIdentity, type StudentCandidate } from "./identity";

const candidates: StudentCandidate[] = [
  {
    lmsStudentId: "syn-student-01",
    fullName: "Student Alpha",
    stableDiscriminator: "profile-01",
  },
  {
    lmsStudentId: "syn-student-02",
    fullName: "Student Beta",
    stableDiscriminator: "profile-02",
  },
];

describe("synthetic student identity resolution", () => {
  it("prefers an exact stable LMS identifier", () => {
    expect(resolveStudentIdentity(candidates, {
      fullName: "Student Alpha",
      lmsStudentId: "syn-student-01",
    })).toEqual(candidates[0]);
  });

  it("does not match a similar name", () => {
    expect(() => resolveStudentIdentity(candidates, {
      fullName: "Student Alph",
    })).toThrow("Student identity is unresolvable");
  });

  it("rejects duplicate names without a stable discriminator", () => {
    const duplicateNames = candidates.map((candidate) => ({
      ...candidate,
      lmsStudentId: undefined,
      stableDiscriminator: undefined,
      fullName: "Student Duplicate",
    }));
    expect(() => resolveStudentIdentity(duplicateNames, {
      fullName: "Student Duplicate",
    })).toThrow("Student identity is unresolvable");
  });

  it("does not depend on row order when a stable identifier exists", () => {
    expect(resolveStudentIdentity([...candidates].reverse(), {
      fullName: "Student Beta",
      lmsStudentId: "syn-student-02",
    })).toEqual(candidates[1]);
  });
});
