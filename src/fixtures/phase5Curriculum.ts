import type { CourseCatalog, SyntheticSession } from "../curriculum/contracts";

export const PHASE5_COURSE_CATALOGS: readonly CourseCatalog[] = [
  {
    courseCode: "SYN-ROBOTICS-FOUNDATION",
    courseName: "Synthetic Robotics Foundation",
    totalSessions: 5,
    entries: [
      {
        sessionNumber: 5,
        lessonTitle: "Synthetic robotics capstone loop",
        lessonContent: [
          "Review synthetic drivetrain tuning",
          "Complete synthetic obstacle routing",
        ],
        homeworkTitle: "Document synthetic capstone observations",
      },
      {
        sessionNumber: 1,
        lessonTitle: "Synthetic robotics kickoff",
        lessonContent: [
          "Identify synthetic robot components",
          "Practice synthetic safety checklist",
        ],
        homeworkTitle: "Label synthetic robot parts",
      },
      {
        sessionNumber: 3,
        lessonTitle: "Synthetic sensor control",
        lessonContent: [
          "Read synthetic distance sensor values",
          "Build synthetic stop-on-object logic",
        ],
        homeworkTitle: "Refine synthetic sensor pseudocode",
      },
    ],
  },
  {
    courseCode: "SYN-PYTHON-FOUNDATION",
    courseName: "Synthetic Python Foundation",
    totalSessions: 3,
    entries: [
      {
        sessionNumber: 1,
        lessonTitle: "Synthetic Python setup",
        lessonContent: [
          "Print synthetic greeting messages",
          "Trace synthetic variable updates",
        ],
        homeworkTitle: "Write synthetic variable practice",
      },
      {
        sessionNumber: 3,
        lessonTitle: "Synthetic Python branching",
        lessonContent: [
          "Compare synthetic score thresholds",
          "Write synthetic if-else flows",
        ],
        homeworkTitle: "Draft synthetic branching exercises",
      },
    ],
  },
];

export const PHASE5_SESSIONS: readonly SyntheticSession[] = [
  {
    id: "synthetic-robotics-session-3",
    classCode: "SYN-ROBOTICS-01",
    courseCode: "SYN-ROBOTICS-FOUNDATION",
    sessionNumber: 3,
    scheduledDate: "2026-08-11",
    startTime: "19:00",
    endTime: "20:30",
    workflowStatus: "context_pending",
  },
  {
    id: "synthetic-robotics-session-5",
    classCode: "SYN-ROBOTICS-01",
    courseCode: "SYN-ROBOTICS-FOUNDATION",
    sessionNumber: 5,
    scheduledDate: "2026-08-25",
    startTime: "19:00",
    endTime: "20:30",
    workflowStatus: "context_pending",
  },
  {
    id: "synthetic-python-session-2",
    classCode: "SYN-PYTHON-02",
    courseCode: "SYN-PYTHON-FOUNDATION",
    sessionNumber: 2,
    scheduledDate: "2026-08-12",
    startTime: "18:00",
    endTime: "19:30",
    workflowStatus: "context_pending",
  },
];
