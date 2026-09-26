import { describe, expect, it } from "vitest";

import {
  PHASE5B_SYNTHETIC_LEARNERS,
  createInitialReviewInputs,
} from "../fixtures/phase5bReviewInputs";
import {
  serializeReviewInputsCsv,
  serializeReviewInputsMarkdown,
} from "./export";

const context = {
  classCode: "SYN-ROBOTICS-01",
  sessionNumber: 3,
  scheduledDate: "2026-08-11",
  startTime: "19:00",
  endTime: "20:30",
} as const;

const inputs = createInitialReviewInputs(PHASE5B_SYNTHETIC_LEARNERS).map((input) =>
  input.rowKey === "synthetic-review-001"
    ? { ...input, attendance: "present" as const, noteDraft: 'Needs, "focus"\nnext' }
    : input,
);

describe("review input exports", () => {
  it("serializes a stable, escaped CSV", () => {
    expect(serializeReviewInputsCsv(PHASE5B_SYNTHETIC_LEARNERS, inputs, context)).toBe(
      [
        "\uFEFFclassCode,sessionNumber,scheduledDate,startTime,endTime,rowKey,displayName,attendance,level,noteDraft",
        'SYN-ROBOTICS-01,3,2026-08-11,19:00,20:30,synthetic-review-001,Synthetic learner 01,present,unknown,"Needs, ""focus""\nnext"',
        "SYN-ROBOTICS-01,3,2026-08-11,19:00,20:30,synthetic-review-002,Synthetic learner 02,unknown,unknown,",
        "SYN-ROBOTICS-01,3,2026-08-11,19:00,20:30,synthetic-review-003,Synthetic learner 03,unknown,unknown,",
        "",
      ].join("\r\n"),
    );
  });

  it("neutralizes spreadsheet formula prefixes in exported text", () => {
    const unsafe = inputs.map((input) =>
      input.rowKey === "synthetic-review-003"
        ? { ...input, noteDraft: "=HYPERLINK(\"https://example.invalid\")" }
        : input,
    );

    expect(serializeReviewInputsCsv(PHASE5B_SYNTHETIC_LEARNERS, unsafe, context)).toContain(
      'synthetic-review-003,Synthetic learner 03,unknown,unknown,"\'=HYPERLINK(""https://example.invalid"")"',
    );
  });

  it("serializes a readable Markdown table and escapes cell delimiters", () => {
    const markdownInputs = inputs.map((input) =>
      input.rowKey === "synthetic-review-002"
        ? { ...input, noteDraft: "Use | safely" }
        : input,
    );
    expect(serializeReviewInputsMarkdown(PHASE5B_SYNTHETIC_LEARNERS, markdownInputs, context)).toContain(
      "| SYN-ROBOTICS-01 | 3 | 2026-08-11 | 19:00 | 20:30 | synthetic-review-002 | Synthetic learner 02 | unknown | unknown | Use \\| safely |",
    );
    expect(serializeReviewInputsMarkdown(PHASE5B_SYNTHETIC_LEARNERS, markdownInputs, context)).toMatch(/^\| Class \| Session/m);
  });

  it("escapes HTML in Markdown cells", () => {
    const markdownInputs = inputs.map((input) =>
      input.rowKey === "synthetic-review-003"
        ? { ...input, noteDraft: "<script>alert('x')</script> & review" }
        : input,
    );

    expect(serializeReviewInputsMarkdown(PHASE5B_SYNTHETIC_LEARNERS, markdownInputs, context)).toContain(
      "&lt;script&gt;alert('x')&lt;/script&gt; &amp; review",
    );
  });

  it("fails closed when stable learner and input keys do not match", () => {
    expect(() => serializeReviewInputsCsv(PHASE5B_SYNTHETIC_LEARNERS, inputs.slice(1), context)).toThrow(
      "mismatched stable row keys",
    );
  });
});
