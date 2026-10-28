from app.domains.matching.preprocessing import StructuredPreprocessor, tokenize
from app.domains.matching.schemas import PreprocessRequest, PreprocessSample


def test_turkish_text_preprocessing_normalizes_and_stems() -> None:
    tokens = tokenize("Yazılımların test süreçlerinde ve otomasyonlarında çalışıyorum.")
    assert "yazilim" in tokens
    assert "test" in tokens
    assert "ve" not in tokens


def test_structured_preprocessing_imputes_and_clips_outliers() -> None:
    request = PreprocessRequest(
        samples=[
            PreprocessSample(
                text="QA Manager fintech deneyimi",
                numeric_features={"years": 12, "team_size": 8},
                categorical_features={"work_mode": "remote"},
            ),
            PreprocessSample(
                text="Senior test lead",
                numeric_features={"years": None, "team_size": 500},
                categorical_features={"work_mode": None},
            ),
        ]
    )

    response = StructuredPreprocessor().preprocess(request)

    assert response.summary.imputed_values["years"] == 12.0
    assert response.numeric_features[1]["years"] == 12.0
    assert response.categorical_features[1]["work_mode"] == "unknown"
    assert response.summary.clipped_outliers["team_size"] >= 1
