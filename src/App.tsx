import { useMemo, useState } from "react";
import {
  assertLmsContext,
  assignStudent,
  canContinueReview,
  getMappingStatus,
  type LmsContext,
  type LmsRosterRow,
} from "./lms/manualMapping";

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

function formatContext(context: LmsContext): string {
  return `${context.scheduledDate} · ${context.startTime}–${context.endTime}`;
}

function statusLabel(status: ReturnType<typeof getMappingStatus>): string {
  if (status === "resolved") return "Resolved";
  if (status === "ambiguous") return "Ambiguous";
  return "Unresolvable";
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
    </main>
  );
}
