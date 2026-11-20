"""Focused unit tests for the API contracts in backend.schemas."""

import pytest
from pydantic import ValidationError

from backend.schemas import (
    AnalysisRequest,
    DiagnosisLLMOutput,
    DiagnosisRequest,
    REPORT_SECTION_TITLES,
    ReportSection,
    ScoutingReport,
    TrendsLLMOutput,
)


def test_analysis_request_accepts_valid_strict_filters() -> None:
    request = AnalysisRequest(
        opponent="BUF",
        down=3,
        exactDistance=8,
        playAction=False,
        passBlockers=6,
        week=4,
    )

    assert request.model_dump()["opponent"] == "BUF"
    assert request.down == 3


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("down", "3"),
        ("down", 5),
        ("exactDistance", 0),
        ("exactDistance", 2.5),
        ("passBlockers", True),
        ("passBlockers", 12),
        ("week", 9),
        ("playAction", 1),
    ],
)
def test_analysis_request_rejects_invalid_field_with_field_location(
    field: str, value: object
) -> None:
    with pytest.raises(ValidationError) as caught:
        AnalysisRequest.model_validate({"opponent": "BUF", field: value})

    assert any(error["loc"] == (field,) for error in caught.value.errors())


def test_analysis_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as caught:
        AnalysisRequest.model_validate({"opponent": "BUF", "unknown": "value"})

    assert caught.value.errors()[0]["loc"] == ("unknown",)
    assert caught.value.errors()[0]["type"] == "extra_forbidden"


def test_diagnosis_request_requires_both_play_identifiers() -> None:
    with pytest.raises(ValidationError) as caught:
        DiagnosisRequest(opponent="BUF", gameId=1)

    assert "playId" in str(caught.value)


def test_llm_outputs_reject_missing_or_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        TrendsLLMOutput.model_validate({"text": "", "facts": []})
    with pytest.raises(ValidationError):
        DiagnosisLLMOutput.model_validate({"hechos": [], "extra": []})


def test_scouting_report_requires_exact_ordered_sections() -> None:
    sections = [
        ReportSection(title=title, text="", languageWarning=False)
        for title in REPORT_SECTION_TITLES
    ]
    report = ScoutingReport(sections=sections)
    assert tuple(section.title for section in report.sections) == REPORT_SECTION_TITLES

    with pytest.raises(ValidationError):
        ScoutingReport(sections=list(reversed(sections)))
