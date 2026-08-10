from mindx_runner.safe_logging import sanitize_log_metadata


def test_safe_logger_removes_credentials_and_personal_text() -> None:
    safe = sanitize_log_metadata(
        {
            "job_id": "00000000-0000-0000-0000-000000000001",
            "password": "not-a-real-password",
            "cookie": "not-a-real-cookie",
            "student_name": "Synthetic Student Alpha",
            "note": "Synthetic private note",
            "records_read": 1,
        }
    )

    assert safe == {
        "job_id": "00000000-0000-0000-0000-000000000001",
        "records_read": 1,
    }


def test_safe_logger_drops_unknown_fields_that_could_hide_personal_text() -> None:
    safe = sanitize_log_metadata(
        {
            "status": "failed",
            "diagnostic": "Synthetic Student Alpha email student@example.invalid",
            "nested": {"records_read": 1},
        }
    )

    assert safe == {"status": "failed"}
