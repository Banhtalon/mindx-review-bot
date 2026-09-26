import type {
  SyntheticLearner,
  SyntheticReviewInput,
} from "./contracts";

export type ReviewExportRow = SyntheticLearner & SyntheticReviewInput;

export type ReviewExportContext = {
  readonly classCode: string;
  readonly sessionNumber: number;
  readonly scheduledDate: string;
  readonly startTime: string;
  readonly endTime: string;
};

function contextCells(context: ReviewExportContext): readonly string[] {
  if (
    context.classCode.trim().length === 0 ||
    !Number.isSafeInteger(context.sessionNumber) ||
    context.sessionNumber < 1 ||
    context.scheduledDate.trim().length === 0 ||
    context.startTime.trim().length === 0 ||
    context.endTime.trim().length === 0
  ) {
    throw new Error("Cannot export review inputs without valid session context");
  }
  return [
    context.classCode,
    String(context.sessionNumber),
    context.scheduledDate,
    context.startTime,
    context.endTime,
  ];
}

function buildExportRows(
  learners: readonly SyntheticLearner[],
  inputs: readonly SyntheticReviewInput[],
): readonly ReviewExportRow[] {
  const learnerKeys = learners.map((learner) => learner.rowKey);
  const inputKeys = inputs.map((input) => input.rowKey);

  if (
    learnerKeys.some((key) => key.trim().length === 0) ||
    new Set(learnerKeys).size !== learnerKeys.length ||
    new Set(inputKeys).size !== inputKeys.length ||
    learnerKeys.length !== inputKeys.length ||
    learnerKeys.some((key) => !inputKeys.includes(key))
  ) {
    throw new Error("Cannot export review inputs with mismatched stable row keys");
  }

  const inputsByKey = new Map(inputs.map((input) => [input.rowKey, input]));
  return learners.map((learner) => ({
    ...learner,
    ...inputsByKey.get(learner.rowKey)!,
  }));
}

function csvCell(value: string): string {
  const safeValue = /^[=+\-@]/u.test(value) ? `'${value}` : value;
  return /[",\r\n]/u.test(safeValue)
    ? `"${safeValue.replaceAll('"', '""')}"`
    : safeValue;
}

function markdownCell(value: string): string {
  const escapedHtml = value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
  return escapedHtml.replaceAll("\\", "\\\\").replaceAll("|", "\\|").replace(/[\r\n]+/gu, "<br>");
}

export function serializeReviewInputsCsv(
  learners: readonly SyntheticLearner[],
  inputs: readonly SyntheticReviewInput[],
  context: ReviewExportContext,
): string {
  const rows = buildExportRows(learners, inputs);
  const header = [
    "classCode",
    "sessionNumber",
    "scheduledDate",
    "startTime",
    "endTime",
    "rowKey",
    "displayName",
    "attendance",
    "level",
    "noteDraft",
  ];
  const fixedContext = contextCells(context);
  const lines = [header, ...rows.map((row) => [
    ...fixedContext,
    row.rowKey,
    row.displayName,
    row.attendance,
    row.level,
    row.noteDraft,
  ])];
  return `\uFEFF${lines.map((line) => line.map(csvCell).join(",")).join("\r\n")}\r\n`;
}

export function serializeReviewInputsMarkdown(
  learners: readonly SyntheticLearner[],
  inputs: readonly SyntheticReviewInput[],
  context: ReviewExportContext,
): string {
  const rows = buildExportRows(learners, inputs);
  const fixedContext = contextCells(context);
  const lines = [
    "| Class | Session | Date | Start | End | Stable ID | Learner | Attendance | Learning level | Draft note |",
    "| --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
    ...rows.map((row) =>
      `| ${[
        ...fixedContext,
        row.rowKey,
        row.displayName,
        row.attendance,
        row.level,
        row.noteDraft,
      ].map(markdownCell).join(" | ")} |`,
    ),
  ];
  return `${lines.join("\n")}\n`;
}
