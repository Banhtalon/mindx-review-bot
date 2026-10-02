from datetime import date, time
from pathlib import Path

import pytest

from mindx_runner.teaching_parser import TeachingParserError, parse_teaching_schedule

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "teaching"


def read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_parser_extracts_normal_week_into_validated_records() -> None:
    batch = parse_teaching_schedule(read_fixture("normal-week.html"))

    assert len(batch.sessions) == 2
    assert batch.sessions[0].class_code == "SYN-ROBOTICS-01"
    assert batch.sessions[0].source_session_id == "teach-sess-001"
    assert batch.sessions[0].verified_internal_id is None
    assert batch.sessions[0].session_number == 3
    assert batch.sessions[0].session_type == "regular"
    assert batch.sessions[0].scheduled_date == date(2026, 8, 17)
    assert batch.sessions[0].start_time == time(9, 0)
    assert batch.sessions[0].end_time == time(10, 30)
    assert batch.sessions[0].teacher_name == "Synthetic Teacher"
    assert len(batch.source_page_hash) == 64
    assert batch.warnings == []


def test_parser_extracts_owner_selected_live_schedule_contract() -> None:
    batch = parse_teaching_schedule(
        read_fixture("live-week.html"), allowed_class_codes={"VT-CSI02"}
    )

    assert len(batch.sessions) == 1
    session = batch.sessions[0]
    assert session.class_code == "VT-CSI02"
    assert session.source_session_id is None
    assert session.session_number == 6
    assert session.session_type == "regular"
    assert session.scheduled_date == date(2026, 9, 27)
    assert session.start_time == time(8, 0)
    assert session.end_time == time(10, 0)
    assert session.block == "Coding"


def test_parser_ignores_invalid_live_time_for_unrelated_class() -> None:
    unrelated = """
          <div class="regular-class" data-block="Coding" data-session-number="99"
            data-special-event="" id="regular-class-unrelated">
            <span>B. 99</span>
            <span class="class-code">OTHER-CLASS</span>
            <span>07:00:00 - 13:00:00</span>
          </div>
"""
    html = read_fixture("live-week.html").replace(
        "          </div>\n        </td>", "          </div>\n" + unrelated + "        </td>", 1
    )

    batch = parse_teaching_schedule(html, allowed_class_codes={"VT-CSI02"})

    assert [session.class_code for session in batch.sessions] == ["VT-CSI02"]


def test_parser_rejects_invalid_live_header_date() -> None:
    html = read_fixture("live-week.html").replace("27/09/2026", "31/02/2026", 1)

    with pytest.raises(TeachingParserError, match="TEACHING_DATA_INVALID"):
        parse_teaching_schedule(html, allowed_class_codes={"VT-CSI02"})


def test_parser_rejects_live_row_width_mismatch() -> None:
    html = read_fixture("live-week.html").replace(
        "        <td></td>\n        <td>\n",
        "        <td>\n",
        1,
    )

    with pytest.raises(TeachingParserError, match="TEACHING_DATA_INVALID"):
        parse_teaching_schedule(html, allowed_class_codes={"VT-CSI02"})


def test_parser_rejects_live_merged_date_header() -> None:
    html = read_fixture("live-week.html").replace(
        '<th>Chủ Nhật 27/09/2026 Hôm nay</th>',
        '<th colspan="2">Chủ Nhật 27/09/2026 Hôm nay</th>',
        1,
    )

    with pytest.raises(TeachingParserError, match="TEACHING_DATA_INVALID"):
        parse_teaching_schedule(html, allowed_class_codes={"VT-CSI02"})


def test_parser_rejects_excessively_nested_live_markup() -> None:
    html = "<div>" * 1100 + read_fixture("live-week.html") + "</div>" * 1100

    with pytest.raises(TeachingParserError, match="TEACHING_DATA_INVALID"):
        parse_teaching_schedule(html, allowed_class_codes={"VT-CSI02"})


def test_parser_uses_live_inner_time_when_it_is_inside_the_row_envelope() -> None:
    html = read_fixture("live-week.html").replace(
        "08:00 - 10:00", "10:00 - 12:00", 1
    ).replace(
        "08:00:00 - 10:00:00", "10:00:00 - 11:30:00", 1
    )

    batch = parse_teaching_schedule(html, allowed_class_codes={"VT-CSI02"})

    assert batch.sessions[0].start_time == time(10, 0)
    assert batch.sessions[0].end_time == time(11, 30)


def test_parser_rejects_live_inner_time_outside_the_row_envelope() -> None:
    html = read_fixture("live-week.html").replace(
        "08:00:00 - 10:00:00", "07:00:00 - 10:00:00", 1
    )

    with pytest.raises(TeachingParserError, match="TEACHING_DATA_INVALID"):
        parse_teaching_schedule(html, allowed_class_codes={"VT-CSI02"})


def test_parser_rejects_live_inner_time_after_the_row_envelope() -> None:
    html = read_fixture("live-week.html").replace(
        "08:00 - 10:00", "10:00 - 12:00", 1
    ).replace(
        "08:00:00 - 10:00:00", "10:00:00 - 12:30:00", 1
    )

    with pytest.raises(TeachingParserError, match="TEACHING_DATA_INVALID"):
        parse_teaching_schedule(html, allowed_class_codes={"VT-CSI02"})


def test_parser_normalizes_live_single_digit_hour() -> None:
    html = read_fixture("live-week.html").replace(
        "08:00 - 10:00", "8:00 - 10:00", 1
    ).replace("08:00:00 - 10:00:00", "8:00:00 - 10:00:00", 1)

    batch = parse_teaching_schedule(html, allowed_class_codes={"VT-CSI02"})

    assert batch.sessions[0].start_time == time(8, 0)


def test_parser_rejects_multiple_live_time_ranges_in_a_row() -> None:
    html = read_fixture("live-week.html").replace(
        "08:00 - 10:00", "08:00 - 10:00 / 09:00 - 11:00", 1
    )

    with pytest.raises(TeachingParserError, match="TEACHING_DATA_INVALID"):
        parse_teaching_schedule(html, allowed_class_codes={"VT-CSI02"})


def test_parser_rejects_duplicate_live_semantic_sessions() -> None:
    duplicate = """
          <div class="regular-class" data-block="Coding" data-session-number="6"
            data-special-event="" id="regular-class-duplicate">
            <span>B. 6</span>
            <span class="class-code">VT-CSI02</span>
          </div>
"""
    html = read_fixture("live-week.html").replace(
        "          </div>\n        </td>",
        "          </div>\n" + duplicate + "        </td>",
        1,
    )

    with pytest.raises(TeachingParserError, match="TEACHING_DUPLICATE_SOURCE_ID"):
        parse_teaching_schedule(html, allowed_class_codes={"VT-CSI02"})


def test_parser_reports_a_real_empty_week_without_error() -> None:
    batch = parse_teaching_schedule(read_fixture("empty-week.html"))

    assert batch.sessions == []
    assert batch.warnings == ["TEACHING_SCHEDULE_EMPTY"]


def test_parser_rejects_an_unmarked_empty_page() -> None:
    with pytest.raises(TeachingParserError, match="TEACHING_DATA_INVALID"):
        parse_teaching_schedule('<main data-teaching-schedule="true"></main>')


def test_parser_rejects_truncated_session_markup() -> None:
    truncated = read_fixture("normal-week.html").replace(
        "</article>", "", 1
    )

    with pytest.raises(TeachingParserError, match="TEACHING_DATA_INVALID"):
        parse_teaching_schedule(truncated)


def test_parser_filters_classes_outside_the_supplied_catalog() -> None:
    batch = parse_teaching_schedule(
        read_fixture("normal-week.html"), allowed_class_codes={"SYN-ROBOTICS-01"}
    )

    assert [session.class_code for session in batch.sessions] == ["SYN-ROBOTICS-01"]


def test_parser_rejects_login_page_instead_of_treating_it_as_empty() -> None:
    with pytest.raises(TeachingParserError, match="TEACHING_LOGIN_REQUIRED"):
        parse_teaching_schedule(read_fixture("login-page.html"))


def test_parser_uses_semantic_attributes_when_generated_css_classes_change() -> None:
    batch = parse_teaching_schedule(read_fixture("css-class-change.html"))

    assert [(session.class_code, session.source_session_id) for session in batch.sessions] == [
        ("SYN-ROBOTICS-01", "teach-sess-001")
    ]


def test_parser_rejects_invalid_schedule_values_with_safe_code() -> None:
    invalid_html = read_fixture("normal-week.html").replace(
        'data-start-time="09:00"', 'data-start-time="not-a-time"', 1
    )

    with pytest.raises(TeachingParserError, match="TEACHING_DATA_INVALID"):
        parse_teaching_schedule(invalid_html)


def test_parser_rejects_duplicate_source_session_ids() -> None:
    duplicate_html = read_fixture("normal-week.html").replace(
        'data-source-session-id="teach-sess-002"',
        'data-source-session-id="teach-sess-001"',
        1,
    )

    with pytest.raises(TeachingParserError, match="TEACHING_DUPLICATE_SOURCE_ID"):
        parse_teaching_schedule(duplicate_html)


def test_parser_rejects_source_ids_that_only_differ_by_whitespace() -> None:
    duplicate_html = read_fixture("normal-week.html").replace(
        'data-source-session-id="teach-sess-002"',
        'data-source-session-id=" teach-sess-001 "',
        1,
    )

    with pytest.raises(TeachingParserError, match="TEACHING_DUPLICATE_SOURCE_ID"):
        parse_teaching_schedule(duplicate_html)


def test_parser_rejects_a_session_that_ends_before_it_starts() -> None:
    invalid_html = read_fixture("normal-week.html").replace(
        'data-end-time="10:30"', 'data-end-time="08:30"', 1
    )

    with pytest.raises(TeachingParserError, match="TEACHING_DATA_INVALID"):
        parse_teaching_schedule(invalid_html)


def test_parser_rejects_a_blank_required_class_code() -> None:
    invalid_html = read_fixture("normal-week.html").replace(
        'data-class-code=" syn-robotics-01 "', 'data-class-code="   "', 1
    )

    with pytest.raises(TeachingParserError, match="TEACHING_DATA_INVALID"):
        parse_teaching_schedule(invalid_html)


def test_parser_hash_is_stable_for_the_same_page_bytes() -> None:
    html = read_fixture("normal-week.html")

    assert parse_teaching_schedule(html).source_page_hash == parse_teaching_schedule(
        html
    ).source_page_hash


def test_parser_preserves_block_and_special_event() -> None:
    batch = parse_teaching_schedule(read_fixture("special-event.html"))

    assert batch.sessions[0].block == "Coding"
    assert batch.sessions[0].special_event == "SYN-EVENT-01"


def test_parser_ignores_unrelated_live_row_with_invalid_or_malformed_time() -> None:
    unrelated_rows = """
      <tr>
        <td>25:00 - 26:00</td>
        <td></td>
        <td>
          <div class="regular-class" data-block="Coding" data-session-number="99"
            data-special-event="" id="regular-class-unrelated-1">
            <span>B. 99</span>
            <span class="class-code">OTHER-CLASS</span>
          </div>
        </td>
      </tr>
      <tr>
        <td>malformed time text</td>
        <td></td>
        <td>
          <div class="regular-class" data-block="Coding" data-session-number="98"
            data-special-event="" id="regular-class-unrelated-2">
            <span>B. 98</span>
            <span class="class-code">OTHER-CLASS-2</span>
          </div>
        </td>
      </tr>
"""
    html = read_fixture("live-week.html").replace(
        "      <tr>\n        <td>08:00 - 10:00</td>",
        unrelated_rows + "      <tr>\n        <td>08:00 - 10:00</td>",
        1,
    )
    batch = parse_teaching_schedule(html, allowed_class_codes={"VT-CSI02"})

    assert len(batch.sessions) == 1
    assert batch.sessions[0].class_code == "VT-CSI02"
    assert batch.sessions[0].start_time == time(8, 0)
    assert batch.sessions[0].end_time == time(10, 0)


def test_parser_ignores_empty_live_row_with_invalid_or_malformed_time() -> None:
    empty_rows = """
      <tr>
        <td>25:00 - 26:00</td>
        <td></td>
        <td></td>
      </tr>
      <tr>
        <td>malformed time text</td>
        <td></td>
        <td></td>
      </tr>
"""
    html = read_fixture("live-week.html").replace(
        "      <tr>\n        <td>08:00 - 10:00</td>",
        empty_rows + "      <tr>\n        <td>08:00 - 10:00</td>",
        1,
    )
    batch = parse_teaching_schedule(html, allowed_class_codes={"VT-CSI02"})

    assert len(batch.sessions) == 1
    assert batch.sessions[0].class_code == "VT-CSI02"
    assert batch.sessions[0].start_time == time(8, 0)


def test_parser_rejects_selected_live_row_with_invalid_or_malformed_time() -> None:
    invalid_clock_html = read_fixture("live-week.html").replace(
        "08:00 - 10:00", "25:00 - 26:00", 1
    )
    with pytest.raises(TeachingParserError, match="TEACHING_DATA_INVALID"):
        parse_teaching_schedule(invalid_clock_html, allowed_class_codes={"VT-CSI02"})

    malformed_text_html = read_fixture("live-week.html").replace(
        "08:00 - 10:00", "malformed-time-text", 1
    )
    with pytest.raises(TeachingParserError, match="TEACHING_DATA_INVALID"):
        parse_teaching_schedule(malformed_text_html, allowed_class_codes={"VT-CSI02"})


def test_parser_ignores_unrelated_synthetic_record_with_malformed_fields() -> None:
    unrelated_session = """
  <article class="generated-card css-older" data-teaching-session="true"
    data-class-code="UNRELATED-CLASS" data-source-session-id="unrelated-sess"
    data-session-number="not-a-number"
    data-scheduled-date="9999-99-99"
    data-start-time="25:00"
    data-end-time="26:00">
    <h3>Unrelated practice</h3>
  </article>
"""
    html = read_fixture("normal-week.html").replace(
        "</main>", unrelated_session + "</main>", 1
    )
    batch = parse_teaching_schedule(
        html, allowed_class_codes={"SYN-ROBOTICS-01"}
    )

    assert len(batch.sessions) == 1
    assert batch.sessions[0].class_code == "SYN-ROBOTICS-01"


def test_parser_normalizes_synthetic_class_code_before_allow_list_check() -> None:
    unrelated_session = """
  <article class="generated-card css-older" data-teaching-session="true"
    data-class-code="  unrelated   code  " data-source-session-id="unrelated-sess"
    data-session-number="not-a-number"
    data-scheduled-date="not-a-date"
    data-start-time="25:00"
    data-end-time="26:00">
  </article>
"""
    html = read_fixture("normal-week.html").replace(
        'data-class-code=" syn-robotics-01 "',
        'data-class-code="  syn   robotics   01  "',
        1,
    ).replace(
        "</main>", unrelated_session + "</main>", 1
    )
    batch = parse_teaching_schedule(
        html, allowed_class_codes={"SYN ROBOTICS 01"}
    )

    assert len(batch.sessions) == 1
    assert batch.sessions[0].class_code == "SYN ROBOTICS 01"


def test_parser_rejects_missing_class_identifier_on_synthetic_record() -> None:
    missing_code_article = """
  <article class="generated-card css-older" data-teaching-session="true"
    data-source-session-id="missing-code-sess"
    data-session-number="1"
    data-scheduled-date="2026-08-17"
    data-start-time="09:00"
    data-end-time="10:30">
  </article>
"""
    html = read_fixture("normal-week.html").replace(
        "</main>", missing_code_article + "</main>", 1
    )
    with pytest.raises(TeachingParserError, match="TEACHING_DATA_INVALID"):
        parse_teaching_schedule(html)


def test_parser_rejects_selected_synthetic_session_with_invalid_session_number() -> None:
    html = read_fixture("normal-week.html").replace(
        'data-session-number="3"', 'data-session-number="not-an-int"', 1
    )
    with pytest.raises(TeachingParserError, match="TEACHING_DATA_INVALID"):
        parse_teaching_schedule(html)


def test_parser_rejects_selected_synthetic_session_with_invalid_date() -> None:
    html = read_fixture("normal-week.html").replace(
        'data-scheduled-date="2026-08-17"', 'data-scheduled-date="2026-02-31"', 1
    )
    with pytest.raises(TeachingParserError, match="TEACHING_DATA_INVALID"):
        parse_teaching_schedule(html)


def test_parser_preserves_raw_class_code_length_limit_for_selected_class() -> None:
    html = read_fixture("normal-week.html").replace(
        'data-class-code=" syn-robotics-01 "',
        'data-class-code="' + " " * 125 + 'syn-robotics-01 "',
        1,
    )
    with pytest.raises(TeachingParserError, match="TEACHING_DATA_INVALID"):
        parse_teaching_schedule(html)
