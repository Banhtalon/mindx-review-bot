/**
 * Strict UTC ISO-8601 calendar date/time validator.
 * Enforces:
 * - Format: YYYY-MM-DDTHH:MM:SSZ or YYYY-MM-DDTHH:MM:SS.sssZ
 * - Real calendar days (handles leap years, 30/31-day months, February 28/29)
 * - Valid hours (0..23, rejecting 24)
 * - Valid minutes (0..59)
 * - Valid seconds (0..59)
 * - Must end in 'Z' (no local time, no timezone offsets like +07:00)
 * - No trailing/leading whitespace or non-canonical characters
 */
export function isValidStrictUtcCalendarIsoTimestamp(val: unknown): boolean {
  if (typeof val !== "string") return false;
  if (val.trim() !== val) return false;
  if (!val) return false;

  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,3}))?Z$/.exec(val);
  if (!match) return false;

  const year = parseInt(match[1], 10);
  const month = parseInt(match[2], 10);
  const day = parseInt(match[3], 10);
  const hour = parseInt(match[4], 10);
  const minute = parseInt(match[5], 10);
  const second = parseInt(match[6], 10);
  const ms = match[7] ? parseInt(match[7].padEnd(3, "0"), 10) : 0;

  if (month < 1 || month > 12) return false;
  if (hour < 0 || hour > 23) return false;
  if (minute < 0 || minute > 59) return false;
  if (second < 0 || second > 59) return false;

  const isLeapYear = (year % 4 === 0 && year % 100 !== 0) || (year % 400 === 0);
  const daysInMonth = [31, isLeapYear ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

  const maxDay = daysInMonth[month - 1];
  if (day < 1 || day > maxDay) return false;

  // Round-trip verification with Date.UTC to ensure JavaScript's engine confirms exact validity
  const date = new Date(Date.UTC(year, month - 1, day, hour, minute, second, ms));
  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day ||
    date.getUTCHours() !== hour ||
    date.getUTCMinutes() !== minute ||
    date.getUTCSeconds() !== second ||
    date.getUTCMilliseconds() !== ms
  ) {
    return false;
  }

  return true;
}
