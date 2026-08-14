import { useCallback, useEffect, useMemo, useState } from "react";
import { PHASE5_COURSE_CATALOGS, PHASE5_SESSIONS } from "./fixtures/phase5Curriculum";
import {
  createInitialReviewInputs,
  PHASE5B_SYNTHETIC_LEARNERS,
} from "./fixtures/phase5bReviewInputs";
import {
  assertLmsContext,
  assignStudent,
  canContinueReview,
  getMappingStatus,
  type LmsContext,
  type LmsRosterRow,
} from "./lms/manualMapping";
import { evaluateReviewInputGate } from "./reviewInputs/gate";
import type {
  AttendanceStatus,
  CommitDraftResult,
  LearningLevel,
  SyntheticLearner,
  SyntheticReviewDraftStore,
  SyntheticReviewDraftSnapshot,
  SyntheticReviewInput,
} from "./reviewInputs/contracts";
import { InMemorySyntheticReviewDraftStore } from "./reviewInputs/syntheticDraftStore";
import { resolveLessonContext } from "./session/lessonContext";
import type { CourseCatalog, LessonContextWarningCode, SyntheticSession } from "./curriculum/contracts";

type InternalStudent = {
  internalId: string;
  fullName: string;
};

const EXPECTED_CONTEXT: LmsContext = {
  classCode: "SYN-ROBOTICS-01",
  sessionNumber: 3,
  scheduledDate: "2026-08-11",
  startTime: "19:00",
  endTime: "20:30",
};

const INTERNAL_STUDENTS: InternalStudent[] = [
  { internalId: "internal-001", fullName: "Student Alpha" },
  { internalId: "internal-002", fullName: "Student Beta" },
  { internalId: "internal-003", fullName: "Student Gamma" },
  { internalId: "internal-004", fullName: "Student Delta" },
];

const LMS_ROWS: LmsRosterRow[] = [
  {
    rowKey: "alpha",
    fullName: "Student Alpha",
    studentId: "syn-01",
    discriminator: "profile-01",
    attendance: "present",
    identityStatus: "resolved",
  },
  {
    rowKey: "beta",
    fullName: "Student Beta",
    discriminator: "profile-02",
    attendance: "online",
    identityStatus: "unresolvable",
  },
  {
    rowKey: "gamma",
    fullName: "Student Gamma",
    attendance: "absent",
    identityStatus: "ambiguous",
  },
];

const ALLOWED_INTERNAL_IDS = new Set(INTERNAL_STUDENTS.map((student) => student.internalId));
const SESSION_NUMBER_WORDS: Record<number, string> = {
  1: "one",
  2: "two",
  3: "three",
  4: "four",
  5: "five",
};

function formatContext(context: LmsContext): string {
  return `${context.scheduledDate} · ${context.startTime}–${context.endTime}`;
}

function formatSyntheticSession(session: { scheduledDate: string; startTime: string; endTime: string }): string {
  return `${session.scheduledDate} · ${session.startTime}–${session.endTime}`;
}

function formatSyntheticLessonSummary(
  catalog: { courseName: string } | undefined,
  session: { courseCode: string; sessionNumber: number },
): string {
  const courseLabel = (catalog?.courseName ?? session.courseCode)
    .replace(/^Synthetic\s+/u, "")
    .replace(/\s+Foundation$/u, "");
  const sessionNumber = SESSION_NUMBER_WORDS[session.sessionNumber] ?? String(session.sessionNumber);

  return `${courseLabel} session ${sessionNumber} synthetic lesson`;
}

function statusLabel(status: ReturnType<typeof getMappingStatus>): string {
  if (status === "resolved") return "Resolved";
  if (status === "ambiguous") return "Ambiguous";
  return "Unresolvable";
}

function lessonContextWarningCopy(warningCode: LessonContextWarningCode) {
  switch (warningCode) {
    case "NEXT_CURRICULUM_MISSING":
      return {
        heading: "Next lesson curriculum unavailable",
        detail: "The actual next synthetic session is shown, but no next lesson content is available in the fixture catalog.",
      };
  }
}

type Phase5ContextSurfaceProps = {
  readonly sessions?: readonly SyntheticSession[];
  readonly courseCatalogs?: readonly CourseCatalog[];
};

export function Phase5ContextSurface({
  sessions = PHASE5_SESSIONS,
  courseCatalogs = PHASE5_COURSE_CATALOGS,
}: Phase5ContextSurfaceProps) {
  const [selectedPhase5SessionId, setSelectedPhase5SessionId] = useState(sessions[0]!.id);

  const selectedSession = useMemo(
    () => sessions.find((session) => session.id === selectedPhase5SessionId) ?? sessions[0]!,
    [selectedPhase5SessionId, sessions],
  );
  const lessonContext = useMemo(
    () => resolveLessonContext(selectedSession, sessions, courseCatalogs),
    [courseCatalogs, selectedSession, sessions],
  );
  const selectedCatalog = useMemo(
    () => courseCatalogs.find((catalog) => catalog.courseCode === selectedSession.courseCode),
    [courseCatalogs, selectedSession],
  );

  return (
    <section className="panel curriculum-panel" aria-labelledby="curriculum-and-session-context">
      <div className="panel-heading">
        <div>
          <h2 id="curriculum-and-session-context">Curriculum and session context</h2>
          <p className="muted">
            Read-only synthetic curriculum context for the selected manual-mapping demo session.
          </p>
        </div>
        <span className="readonly-badge">Synthetic read-only</span>
      </div>

      <div className="curriculum-layout">
        <div className="curriculum-session-list" role="group" aria-label="Synthetic sessions">
          {sessions.map((session) => {
            const isSelected = session.id === selectedSession.id;

            return (
              <button
                key={session.id}
                type="button"
                className={isSelected ? "session-option selected" : "session-option"}
                aria-pressed={isSelected}
                aria-label={`Select ${session.classCode} session ${session.sessionNumber}`}
                onClick={() => setSelectedPhase5SessionId(session.id)}
              >
                <strong>{session.classCode} · S#{session.sessionNumber}</strong>
                <span>{formatSyntheticSession(session)}</span>
                <span>{session.workflowStatus}</span>
              </button>
            );
          })}
        </div>

        <div className="curriculum-context">
          <div className="context-metadata-grid">
            <div className="context-box">
              <span className="context-label">Selected session</span>
              <strong>{selectedSession.classCode} · Session {selectedSession.sessionNumber}</strong>
              <span>{formatSyntheticSession(selectedSession)}</span>
            </div>
            <div className="context-box">
              <span className="context-label">Course catalog</span>
              <strong>{selectedCatalog?.courseName ?? selectedSession.courseCode}</strong>
              <span>{selectedCatalog?.totalSessions ?? "Unknown"} total synthetic sessions</span>
            </div>
          </div>

          <div className="lesson-card-grid">
            {lessonContext.currentLesson && (
              <article className="lesson-card">
                <span className="context-label">Current card</span>
                <h3>Current lesson</h3>
                <p className="lesson-title">{formatSyntheticLessonSummary(selectedCatalog, selectedSession)}</p>
                <p className="muted">{lessonContext.currentLesson.lessonTitle}</p>
                <ul className="lesson-content-list">
                  {lessonContext.currentLesson.lessonContent.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
                {lessonContext.currentLesson.homeworkTitle && (
                  <p className="muted">Homework: {lessonContext.currentLesson.homeworkTitle}</p>
                )}
              </article>
            )}

            {lessonContext.nextSession && (
              <article className="lesson-card">
                <span className="context-label">Next card</span>
                <h3>Next actual session</h3>
                <p className="lesson-title">
                  {lessonContext.nextSession.classCode} · Session {lessonContext.nextSession.sessionNumber}
                </p>
                <p className="muted">{formatSyntheticSession(lessonContext.nextSession)}</p>
                {lessonContext.nextLesson ? (
                  <ul className="lesson-content-list">
                    <li>{lessonContext.nextLesson.lessonTitle}</li>
                    {lessonContext.nextLesson.homeworkTitle ? (
                      <li>Homework: {lessonContext.nextLesson.homeworkTitle}</li>
                    ) : null}
                  </ul>
                ) : (
                  <p className="muted">Next curriculum entry is intentionally unavailable.</p>
                )}
              </article>
            )}
          </div>

          {lessonContext.status === "no_next_session" && (
            <div className="alert context-warning" role="status">
              <strong>No next lesson is scheduled</strong>
              <span>The selected synthetic session is the latest actual session in this read-only fixture.</span>
            </div>
          )}

          {lessonContext.status === "curriculum_missing" && (
            <div className="alert context-warning" role="status">
              <strong>Curriculum unavailable</strong>
              <span>The selected synthetic session has no current lesson entry in the immutable fixture catalog.</span>
            </div>
          )}

          {lessonContext.warnings.map((warningCode) => {
            const warning = lessonContextWarningCopy(warningCode);

            return (
              <div className="alert context-warning" role="status" key={warningCode}>
                <h3>{warning.heading}</h3>
                <strong>{warningCode}</strong>
                <span>{warning.detail}</span>
              </div>
            );
          })}

          {lessonContext.status === "manual_fallback" && (
            <div className="alert context-warning" role="status">
              <h3>Context requires manual review</h3>
              <strong>{lessonContext.reasonCode}</strong>
              <span>No next lesson is shown because the synthetic session context is ambiguous or invalid.</span>
            </div>
          )}

        </div>
      </div>
    </section>
  );
}

type Phase5BReviewInputSurfaceProps = {
  readonly learners?: readonly SyntheticLearner[];
  readonly store?: SyntheticReviewDraftStore;
};

type ReviewInputPatch = Partial<Pick<SyntheticReviewInput, "attendance" | "level" | "noteDraft">>;
type DraftCommitStatus = "saved" | "pending" | "conflict";

export function Phase5BReviewInputSurface({
  learners = PHASE5B_SYNTHETIC_LEARNERS,
  store: suppliedStore,
}: Phase5BReviewInputSurfaceProps) {
  const [draftStore] = useState<SyntheticReviewDraftStore>(() =>
    suppliedStore ??
    new InMemorySyntheticReviewDraftStore(
      "synthetic-robotics-session-3",
      createInitialReviewInputs(learners),
    ),
  );
  const [initialSnapshot] = useState<SyntheticReviewDraftSnapshot>(() => draftStore.read());
  const [inputs, setInputs] = useState<readonly SyntheticReviewInput[]>(initialSnapshot.inputs);
  const [revision, setRevision] = useState(initialSnapshot.revision);
  const [commitStatus, setCommitStatus] = useState<DraftCommitStatus>("saved");
  const [conflictSnapshot, setConflictSnapshot] = useState<SyntheticReviewDraftSnapshot | null>(null);
  const gate = useMemo(() => evaluateReviewInputGate(inputs), [inputs]);

  const applyCommitResult = useCallback((result: CommitDraftResult) => {
    if (result.status === "saved") {
      setRevision(result.snapshot.revision);
      setConflictSnapshot(null);
      setCommitStatus("saved");
      return;
    }

    setConflictSnapshot(result.current);
    setCommitStatus("conflict");
  }, []);

  useEffect(() => {
    if (commitStatus !== "pending") return;

    const timeoutId = window.setTimeout(() => {
      applyCommitResult(draftStore.commitDraft(revision, inputs));
    }, 300);

    return () => window.clearTimeout(timeoutId);
  }, [applyCommitResult, commitStatus, draftStore, inputs, revision]);

  function markPendingUnlessConflicted() {
    setCommitStatus((current) => (current === "conflict" ? current : "pending"));
  }

  function updateInput(rowKey: string, patch: ReviewInputPatch) {
    setInputs((current) =>
      current.map((input) => (input.rowKey === rowKey ? { ...input, ...patch } : input)),
    );
    markPendingUnlessConflicted();
  }

  function markAllPresent() {
    setInputs((current) =>
      current.map((input) => ({ ...input, attendance: "present" as const })),
    );
    markPendingUnlessConflicted();
  }

  function useLatestVersion() {
    const latest = draftStore.read();
    setInputs(latest.inputs);
    setRevision(latest.revision);
    setConflictSnapshot(null);
    setCommitStatus("saved");
  }

  function keepLocalDraft() {
    const latest = draftStore.read();
    applyCommitResult(draftStore.commitDraft(latest.revision, inputs));
  }

  return (
    <section className="panel review-inputs-panel" aria-labelledby="synthetic-review-inputs-heading">
      <div className="panel-heading">
        <div>
          <h2 id="synthetic-review-inputs-heading">Synthetic review inputs</h2>
          <p className="muted">
            Synthetic in-memory draft with debounced local autosave. A full reload intentionally resets these values.
          </p>
        </div>
        <span className="readonly-badge">Synthetic local draft</span>
      </div>

      <div className="review-inputs-toolbar">
        <p className="muted">Attendance is required before a later review-generation phase can continue.</p>
        <button className="secondary-button" type="button" onClick={markAllPresent}>
          Mark all present
        </button>
      </div>

      <div
        className={`review-input-gate ${gate.ready ? "ready" : "blocked"}`}
        role="status"
        aria-live="polite"
      >
        <strong>
          {gate.ready ? "Generation ready: attendance complete" : "Generation blocked: attendance unknown"}
        </strong>
        <span>
          {gate.ready
            ? `All ${learners.length} synthetic learners have explicit attendance.`
            : `Reason code: ${gate.reasonCode} · ${gate.unknownAttendanceRowKeys.length} attendance value(s) unresolved.`}
        </span>
      </div>

      <div className={`review-draft-status ${commitStatus}`} role="status" aria-live="polite">
        <strong>
          {commitStatus === "pending"
            ? "Draft pending"
            : commitStatus === "conflict"
              ? "Autosave paused"
              : `Saved locally · revision ${revision}`}
        </strong>
        <span>Synthetic in-memory draft only. A full reload resets it.</span>
      </div>

      {conflictSnapshot ? (
        <div className="review-draft-conflict" role="alert">
          <strong>Conflict detected · local draft preserved</strong>
          <p>
            Synthetic revision {conflictSnapshot.revision} is newer. Choose which draft to continue with;
            nothing is written to Teaching or LMS.
          </p>
          <div className="review-draft-conflict-actions">
            <button className="secondary-button" type="button" onClick={useLatestVersion}>
              Use latest version
            </button>
            <button className="secondary-button" type="button" onClick={keepLocalDraft}>
              Keep my local draft
            </button>
          </div>
        </div>
      ) : null}

      <div className="review-inputs-list">
        {learners.map((learner) => {
          const input = inputs.find((candidate) => candidate.rowKey === learner.rowKey);

          if (!input) return null;

          const attendanceLabel = `${learner.displayName} attendance`;
          const levelLabel = `${learner.displayName} level`;
          const noteLabel = `${learner.displayName} draft note`;

          return (
            <fieldset className="review-input-card" key={learner.rowKey}>
              <legend>{learner.displayName}</legend>
              <div className="review-input-control-grid">
                <label className="review-input-field" htmlFor={`${learner.rowKey}-attendance`}>
                  <span>Attendance</span>
                  <select
                    id={`${learner.rowKey}-attendance`}
                    aria-label={attendanceLabel}
                    value={input.attendance}
                    onChange={(event) =>
                      updateInput(learner.rowKey, {
                        attendance: event.currentTarget.value as AttendanceStatus,
                      })
                    }
                  >
                    <option value="unknown">Unknown</option>
                    <option value="present">Present</option>
                    <option value="absent">Absent</option>
                  </select>
                </label>

                <label className="review-input-field" htmlFor={`${learner.rowKey}-level`}>
                  <span>Learning level</span>
                  <select
                    id={`${learner.rowKey}-level`}
                    aria-label={levelLabel}
                    value={input.level}
                    onChange={(event) =>
                      updateInput(learner.rowKey, {
                        level: event.currentTarget.value as LearningLevel,
                      })
                    }
                  >
                    <option value="unknown">Unknown</option>
                    <option value="strong">Strong</option>
                    <option value="developing">Developing</option>
                    <option value="needs_support">Needs support</option>
                  </select>
                </label>

                <label className="review-input-field review-input-note" htmlFor={`${learner.rowKey}-note`}>
                  <span>Draft note</span>
                  <textarea
                    id={`${learner.rowKey}-note`}
                    aria-label={noteLabel}
                    rows={3}
                    value={input.noteDraft}
                    onChange={(event) => updateInput(learner.rowKey, { noteDraft: event.currentTarget.value })}
                  />
                </label>
              </div>
            </fieldset>
          );
        })}
      </div>
    </section>
  );
}

export default function App() {
  const [contextMismatch, setContextMismatch] = useState(false);
  const [assignments, setAssignments] = useState<Record<string, string>>({});
  const observedContext = contextMismatch
    ? { ...EXPECTED_CONTEXT, classCode: "SYN-ROBOTICS-01B", sessionNumber: 4, startTime: "20:30" }
    : EXPECTED_CONTEXT;
  const contextAssertion = useMemo(
    () => assertLmsContext(EXPECTED_CONTEXT, observedContext),
    [observedContext],
  );
  const rowStatuses = LMS_ROWS.map((row) => ({
    row,
    status: getMappingStatus(row, assignments),
  }));
  const reviewCanContinue = canContinueReview(
    contextAssertion,
    rowStatuses.map(({ status }) => status),
  );
  const unresolvedCount = rowStatuses.filter(({ status }) => status !== "resolved").length;

  function handleAssignment(rowKey: string, internalId: string) {
    setAssignments((current) => {
      if (!internalId) {
        const next = { ...current };
        delete next[rowKey];
        return next;
      }
      return assignStudent(current, rowKey, internalId, ALLOWED_INTERNAL_IDS);
    });
  }

  return (
    <main className="review-app">
      <header className="app-header">
        <div>
          <p className="eyebrow">MindX Review Bot</p>
          <h1>MindX Review Bot</h1>
          <p className="screen-title">LMS context review</p>
          <p className="muted">Synthetic-ready Spike 0</p>
          <p className="muted">LMS write actions disabled</p>
        </div>
        <span className="readonly-badge">Read-only · synthetic demo</span>
      </header>

      <Phase5ContextSurface />

      <nav className="workflow" aria-label="Review progress">
        <span className="workflow-step active">1. Chọn pending session</span>
        <span className="workflow-step active">2. Kiểm tra context</span>
        <span className="workflow-step">3. Mapping học viên</span>
      </nav>

      <div className="review-grid">
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h2>Session đang chờ xử lý</h2>
              <p className="muted">Chỉ chọn ca đã kết thúc và còn ở trạng thái context_pending.</p>
            </div>
            <span className="status success">Đủ điều kiện</span>
          </div>
          <button className="session-option selected" type="button" aria-pressed="true">
            <strong>SYN-ROBOTICS-01 · Session 3</strong>
            <span>Hôm qua · 4 học viên · context_pending</span>
          </button>
          <button className="session-option" type="button" aria-pressed="false">
            <strong>SYN-PYTHON-02 · Session 8</strong>
            <span>Hôm nay · 3 học viên · context_pending</span>
          </button>
        </section>

        <aside className="panel safety-panel">
          <div className="panel-heading">
            <div>
              <h2>Trạng thái an toàn</h2>
              <p className="muted">Điều kiện để chuyển sang mapping.</p>
            </div>
          </div>
          <ul className="status-list">
            <li><span className="status-dot success" /> Session đã kết thúc</li>
            <li><span className={`status-dot ${contextAssertion.matched ? "success" : "warning"}`} /> Context exact match</li>
            <li><span className="status-dot warning" /> {unresolvedCount} mapping cần xử lý</li>
          </ul>
          <p className="explanation">Mục đích: chặn việc gắn nhầm nhận xét vào sai ca hoặc sai học viên trước các phase tạo nội dung.</p>
        </aside>
      </div>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Đối chiếu LMS context</h2>
            <p className="muted">Class, session, ngày và giờ phải khớp tuyệt đối.</p>
          </div>
          <span className={`status ${contextAssertion.matched ? "success" : "danger"}`}>
            {contextAssertion.matched ? "Context khớp" : "Context mismatch"}
          </span>
        </div>
        <div className="context-grid">
          <div className="context-box">
            <span className="context-label">Expected</span>
            <strong>{EXPECTED_CONTEXT.classCode} · Session {EXPECTED_CONTEXT.sessionNumber}</strong>
            <span>{formatContext(EXPECTED_CONTEXT)}</span>
          </div>
          <div className={`context-box ${contextAssertion.matched ? "observed" : "mismatch"}`}>
            <span className="context-label">Observed · LMS</span>
            <strong>{observedContext.classCode} · Session {observedContext.sessionNumber}</strong>
            <span>{formatContext(observedContext)}</span>
          </div>
        </div>
        {!contextAssertion.matched && (
          <div className="alert" role="alert">
            <strong>Manual fallback bắt buộc</strong>
            <span>{contextAssertion.reasonCode} — chọn lại session hoặc dừng xử lý.</span>
          </div>
        )}
        <div className="button-row">
          <button
            className="secondary-button"
            type="button"
            onClick={() => setContextMismatch((current) => !current)}
          >
            {contextMismatch ? "Khôi phục context khớp" : "Xem trạng thái context sai"}
          </button>
        </div>
      </section>

      <section className="panel roster-panel">
        <div className="panel-heading">
          <div>
            <h2>Mapping học viên</h2>
            <p className="muted">Một dòng chưa giải quyết thì chưa được phép tiếp tục.</p>
          </div>
          <span className="status warning">{unresolvedCount} cần chọn</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>LMS roster</th><th>Stable signal</th><th>Attendance</th><th>Internal student</th><th>Status</th></tr>
            </thead>
            <tbody>
              {rowStatuses.map(({ row, status }) => {
                const assignment = assignments[row.rowKey];
                const selectedStudent = INTERNAL_STUDENTS.find((student) => student.internalId === assignment);
                const assignedToOtherRow = new Set(
                  Object.entries(assignments)
                    .filter(([assignedRowKey]) => assignedRowKey !== row.rowKey)
                    .map(([, internalId]) => internalId),
                );
                return (
                  <tr key={row.rowKey}>
                    <td><strong>{row.fullName}</strong><small>LMS display name</small></td>
                    <td><code>{row.studentId ?? row.discriminator ?? "2 candidates"}</code></td>
                    <td>{row.attendance}</td>
                    <td>
                      {status === "resolved" && selectedStudent ? (
                        <span><strong>{selectedStudent.fullName}</strong><small>{selectedStudent.internalId}</small></span>
                      ) : status === "resolved" ? (
                        <span><strong>{row.fullName}</strong><small>stable internal mapping</small></span>
                      ) : (
                        <select
                          aria-label={`Map ${row.fullName}`}
                          value={assignment ?? ""}
                          onChange={(event) => handleAssignment(row.rowKey, event.target.value)}
                        >
                          <option value="">Chọn internal student…</option>
                          {INTERNAL_STUDENTS.filter((student) =>
                            student.internalId === assignment || !assignedToOtherRow.has(student.internalId),
                          ).map((student) => (
                            <option key={student.internalId} value={student.internalId}>{student.fullName} · {student.internalId}</option>
                          ))}
                        </select>
                      )}
                    </td>
                    <td><span className={`status ${status === "resolved" ? "success" : status === "ambiguous" ? "danger" : "warning"}`}>{statusLabel(status)}</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <footer className="panel-footer">
          <span className="muted">Chưa có dữ liệu thật và chưa ghi thay đổi lên LMS.</span>
          <button className="primary-button" type="button" disabled={!reviewCanContinue}>Tiếp tục khi đã giải quyết</button>
        </footer>
      </section>

      <Phase5BReviewInputSurface />
    </main>
  );
}
