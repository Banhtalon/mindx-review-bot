from mindx_runner.lms_identity import (
    ExpectedStudent,
    StudentResolution,
    resolve_lms_student,
)
from mindx_runner.lms_models import LmsRosterRow


def row(
    *,
    student_id: str | None,
    discriminator: str | None,
    full_name: str,
    attendance: str = "present",
) -> LmsRosterRow:
    return LmsRosterRow(
        student_id=student_id,
        discriminator=discriminator,
        full_name=full_name,
        attendance=attendance,  # type: ignore[arg-type]
    )


def test_resolves_by_exact_student_id() -> None:
    result = resolve_lms_student(
        ExpectedStudent(
            internal_id="internal-001",
            student_id=" std-002 ",
            discriminator=None,
            full_name="Nguyễn Hà",
        ),
        (
            row(student_id="std-001", discriminator="disc-001", full_name="Nguyễn Hà"),
            row(student_id="std-002", discriminator="disc-002", full_name="Nguyễn Hà"),
        ),
    )

    assert result == StudentResolution(
        internal_id="internal-001",
        status="resolved",
        reason_code="LMS_STUDENT_ID_MATCH",
    )


def test_resolves_by_exact_discriminator_when_student_id_missing() -> None:
    result = resolve_lms_student(
        ExpectedStudent(
            internal_id="internal-002",
            student_id=None,
            discriminator=" disc-020 ",
            full_name="Lê Minh",
        ),
        (
            row(student_id="std-020", discriminator="disc-020", full_name="Lê Minh"),
            row(student_id="std-021", discriminator="disc-021", full_name="Lê Minh"),
        ),
    )

    assert result == StudentResolution(
        internal_id="internal-002",
        status="resolved",
        reason_code="LMS_STUDENT_DISCRIMINATOR_MATCH",
    )


def test_resolves_when_student_id_and_discriminator_agree_on_same_row() -> None:
    result = resolve_lms_student(
        ExpectedStudent(
            internal_id="internal-002a",
            student_id="std-022",
            discriminator="disc-022",
            full_name="Lê Minh",
        ),
        (
            row(student_id="std-022", discriminator="disc-022", full_name="Lê Minh"),
            row(student_id="std-023", discriminator="disc-023", full_name="Lê Minh"),
        ),
    )

    assert result == StudentResolution(
        internal_id="internal-002a",
        status="resolved",
        reason_code="LMS_STUDENT_ID_MATCH",
    )


def test_conflicting_student_id_and_discriminator_fail_closed() -> None:
    result = resolve_lms_student(
        ExpectedStudent(
            internal_id="internal-002b",
            student_id="std-024",
            discriminator="disc-025",
            full_name="Lê Minh",
        ),
        (
            row(student_id="std-024", discriminator="disc-024", full_name="Lê Minh"),
            row(student_id="std-025", discriminator="disc-025", full_name="Lê Minh"),
        ),
    )

    assert result == StudentResolution(
        internal_id=None,
        status="unresolvable",
        reason_code="LMS_STUDENT_IDENTITY_UNRESOLVABLE",
    )


def test_resolves_by_exact_name_only_when_one_candidate_has_stable_identity() -> None:
    result = resolve_lms_student(
        ExpectedStudent(
            internal_id="internal-003",
            student_id=None,
            discriminator=None,
            full_name="  nguyễn   THU  ",
        ),
        (
            row(student_id="std-030", discriminator=None, full_name="Nguyễn Thu"),
            row(student_id=None, discriminator=None, full_name="Trần Vy"),
        ),
    )

    assert result == StudentResolution(
        internal_id="internal-003",
        status="resolved",
        reason_code="LMS_STUDENT_NAME_MATCH",
    )


def test_does_not_fuzzy_match_similar_names() -> None:
    result = resolve_lms_student(
        ExpectedStudent(
            internal_id="internal-004",
            student_id=None,
            discriminator=None,
            full_name="Nguyễn An",
        ),
        (row(student_id="std-040", discriminator="disc-040", full_name="Nguyễn Anh"),),
    )

    assert result == StudentResolution(
        internal_id=None,
        status="unresolvable",
        reason_code="LMS_STUDENT_IDENTITY_UNRESOLVABLE",
    )


def test_duplicate_names_with_distinct_ids_still_resolve_by_stable_id() -> None:
    rows = (
        row(student_id="std-050", discriminator="disc-050", full_name="Phạm Linh"),
        row(student_id="std-051", discriminator="disc-051", full_name="Phạm Linh"),
    )

    assert resolve_lms_student(
        ExpectedStudent(
            internal_id="internal-005",
            student_id="std-051",
            discriminator=None,
            full_name="Phạm Linh",
        ),
        rows,
    ) == StudentResolution(
        internal_id="internal-005",
        status="resolved",
        reason_code="LMS_STUDENT_ID_MATCH",
    )


def test_duplicate_names_without_stable_identity_are_unresolvable() -> None:
    result = resolve_lms_student(
        ExpectedStudent(
            internal_id="internal-006",
            student_id=None,
            discriminator=None,
            full_name="Phạm Linh",
        ),
        (
            row(student_id=None, discriminator=None, full_name="Phạm Linh"),
            row(student_id=None, discriminator=None, full_name="Phạm Linh"),
        ),
    )

    assert result == StudentResolution(
        internal_id=None,
        status="unresolvable",
        reason_code="LMS_STUDENT_IDENTITY_UNRESOLVABLE",
    )


def test_duplicate_non_null_page_ids_are_ambiguous_before_matching() -> None:
    result = resolve_lms_student(
        ExpectedStudent(
            internal_id="internal-007",
            student_id="std-070",
            discriminator=None,
            full_name="Student Seven",
        ),
        (
            row(student_id="std-070", discriminator="disc-070", full_name="Student Seven"),
            row(student_id=" std-070 ", discriminator="disc-071", full_name="Student Eight"),
        ),
    )

    assert result == StudentResolution(
        internal_id=None,
        status="ambiguous",
        reason_code="LMS_STUDENT_IDENTITY_AMBIGUOUS",
    )


def test_duplicate_non_null_discriminators_are_ambiguous_before_matching() -> None:
    result = resolve_lms_student(
        ExpectedStudent(
            internal_id="internal-007b",
            student_id=None,
            discriminator="disc-072",
            full_name="Student Nine",
        ),
        (
            row(student_id="std-072", discriminator="disc-072", full_name="Student Eight"),
            row(
                student_id="std-073",
                discriminator=" disc-072 ",
                full_name="Student Nine",
            ),
        ),
    )

    assert result == StudentResolution(
        internal_id=None,
        status="ambiguous",
        reason_code="LMS_STUDENT_IDENTITY_AMBIGUOUS",
    )


def test_resolution_is_row_order_invariant() -> None:
    expected = ExpectedStudent(
        internal_id="internal-008",
        student_id=None,
        discriminator="disc-081",
        full_name="Student Eight",
    )
    rows = (
        row(student_id="std-080", discriminator="disc-080", full_name="Student Seven"),
        row(student_id="std-081", discriminator="disc-081", full_name="Student Eight"),
        row(student_id="std-082", discriminator="disc-082", full_name="Student Nine"),
    )

    first = resolve_lms_student(expected, rows)
    reordered = resolve_lms_student(expected, tuple(reversed(rows)))

    assert first == StudentResolution(
        internal_id="internal-008",
        status="resolved",
        reason_code="LMS_STUDENT_DISCRIMINATOR_MATCH",
    )
    assert reordered == first
