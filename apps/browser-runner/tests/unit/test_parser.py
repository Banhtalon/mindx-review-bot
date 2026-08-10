from mindx_runner.parser import parse_student_rows, resolve_student


def test_parser_extracts_synthetic_student_rows_without_row_identity() -> None:
    html = """
    <section data-class-code="SYN-CLASS-01" data-session-number="3">
      <div data-student-id="syn-02" data-discriminator="profile-02">Student Beta</div>
      <div data-student-id="syn-01" data-discriminator="profile-01">Student Alpha</div>
    </section>
    """

    rows = parse_student_rows(html)

    assert rows[0].student_id == "syn-02"
    assert rows[1].student_id == "syn-01"
    assert resolve_student(rows, student_id="syn-01").full_name == "Student Alpha"


def test_duplicate_synthetic_names_without_discriminator_are_unresolvable() -> None:
    html = """
    <section>
      <div>Student Duplicate</div>
      <div>Student Duplicate</div>
    </section>
    """

    rows = parse_student_rows(html)

    try:
        resolve_student(rows, full_name="Student Duplicate")
    except RuntimeError as error:
        assert str(error) == "Student identity is unresolvable"
    else:
        raise AssertionError("expected duplicate name to be unresolvable")
