from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from statistics import mean

from .schemas import (
    CandidateProfileInput,
    JobPostingInput,
    PreprocessRequest,
    PreprocessResponse,
    StructuredFeatureSummary,
)

TURKISH_STOP_WORDS = {
    "acaba",
    "ama",
    "ancak",
    "aslında",
    "az",
    "bazı",
    "belki",
    "bile",
    "bir",
    "birkaç",
    "biz",
    "bu",
    "çok",
    "çünkü",
    "da",
    "daha",
    "de",
    "defa",
    "diye",
    "en",
    "gibi",
    "hem",
    "hep",
    "hepsi",
    "her",
    "hiç",
    "için",
    "ile",
    "ise",
    "kez",
    "ki",
    "kim",
    "mı",
    "mu",
    "mü",
    "nasıl",
    "ne",
    "neden",
    "nerede",
    "niçin",
    "o",
    "sanki",
    "şey",
    "siz",
    "şu",
    "tüm",
    "ve",
    "veya",
    "ya",
    "yani",
}

COMMON_SUFFIXES = [
    "lerinde",
    "larinda",
    "larinde",
    "lerinde",
    "sinde",
    "sinda",
    "larin",
    "lerin",
    "larini",
    "lerini",
    "lari",
    "leri",
    "lerden",
    "lardan",
    "lerin",
    "ların",
    "leri",
    "ları",
    "larımız",
    "lerimiz",
    "lardan",
    "lerden",
    "lik",
    "lık",
    "luk",
    "lük",
    "ci",
    "cı",
    "cu",
    "cü",
    "siz",
    "sız",
    "suz",
    "süz",
    "lar",
    "ler",
    "nde",
    "nda",
    "inde",
    "inda",
    "unda",
    "unde",
    "daki",
    "deki",
    "daki",
    "li",
    "lı",
    "lu",
    "lü",
]


def normalize_turkish_text(text: str) -> str:
    lowered = text.casefold()
    lowered = (
        lowered.replace("ı", "i")
        .replace("ğ", "g")
        .replace("ü", "u")
        .replace("ş", "s")
        .replace("ö", "o")
        .replace("ç", "c")
    )
    normalized = unicodedata.normalize("NFKD", lowered)
    sanitized = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    sanitized = re.sub(r"[^a-z0-9\s#+/-]", " ", sanitized)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    return sanitized


def stem_token(token: str) -> str:
    for suffix in sorted(COMMON_SUFFIXES, key=len, reverse=True):
        if token.endswith(suffix) and len(token) > len(suffix) + 2:
            return token[: -len(suffix)]
    return token


def tokenize(text: str) -> list[str]:
    tokens = normalize_turkish_text(text).split()
    cleaned = [
        stem_token(token)
        for token in tokens
        if token not in TURKISH_STOP_WORDS and len(token) > 1
    ]
    return cleaned


@dataclass
class PreparedDocument:
    normalized_text: str
    tokens: list[str]


class TextPreprocessor:
    def prepare(self, text: str) -> PreparedDocument:
        normalized = normalize_turkish_text(text)
        return PreparedDocument(normalized_text=normalized, tokens=tokenize(normalized))

    def compose_candidate_text(self, candidate: CandidateProfileInput) -> str:
        parts = [
            candidate.headline,
            candidate.summary,
            " ".join(candidate.skills),
            " ".join(candidate.industries),
            " ".join(candidate.certifications),
            " ".join(candidate.languages),
            candidate.raw_text,
        ]
        return " ".join(part for part in parts if part)

    def compose_job_text(self, job: JobPostingInput) -> str:
        parts = [
            job.title,
            job.description,
            job.requirements,
            " ".join(job.required_skills),
            " ".join(job.preferred_skills),
            " ".join(job.industries),
            job.raw_text,
        ]
        return " ".join(part for part in parts if part)


class StructuredPreprocessor:
    def preprocess(self, request: PreprocessRequest) -> PreprocessResponse:
        numeric_keys = self._collect_numeric_keys(request)
        categorical_keys = self._collect_categorical_keys(request)
        numeric_imputations = self._calculate_numeric_imputations(request, numeric_keys)
        outlier_limits = self._estimate_outlier_limits(request, numeric_keys)
        vocabularies = {
            key: sorted(
                {
                    sample.categorical_features.get(key) or "unknown"
                    for sample in request.samples
                }
            )
            for key in categorical_keys
        }

        normalized_texts: list[str] = []
        cleaned_tokens: list[list[str]] = []
        normalized_numeric: list[dict[str, float]] = []
        normalized_categorical: list[dict[str, str]] = []
        clipped_outliers = {key: 0 for key in numeric_keys}

        for sample in request.samples:
            prepared = normalize_turkish_text(sample.text)
            normalized_texts.append(prepared)
            cleaned_tokens.append(tokenize(prepared))

            numeric_values: dict[str, float] = {}
            for key in numeric_keys:
                raw_value = sample.numeric_features.get(key)
                value = (
                    numeric_imputations[key] if raw_value is None else float(raw_value)
                )
                lower, upper = outlier_limits[key]
                clipped_value = min(max(value, lower), upper)
                if clipped_value != value:
                    clipped_outliers[key] += 1
                numeric_values[key] = round(clipped_value, 6)
            normalized_numeric.append(numeric_values)

            categorical_values = {
                key: sample.categorical_features.get(key) or "unknown"
                for key in categorical_keys
            }
            normalized_categorical.append(categorical_values)

        summary = StructuredFeatureSummary(
            imputed_values=numeric_imputations,
            clipped_outliers=clipped_outliers,
            categorical_vocabularies=vocabularies,
        )
        return PreprocessResponse(
            normalized_texts=normalized_texts,
            cleaned_tokens=cleaned_tokens,
            numeric_features=normalized_numeric,
            categorical_features=normalized_categorical,
            summary=summary,
        )

    def _collect_numeric_keys(self, request: PreprocessRequest) -> list[str]:
        keys: set[str] = set()
        for sample in request.samples:
            keys.update(sample.numeric_features)
        return sorted(keys)

    def _collect_categorical_keys(self, request: PreprocessRequest) -> list[str]:
        keys: set[str] = set()
        for sample in request.samples:
            keys.update(sample.categorical_features)
        return sorted(keys)

    def _calculate_numeric_imputations(
        self, request: PreprocessRequest, keys: list[str]
    ) -> dict[str, float]:
        values: dict[str, list[float]] = {key: [] for key in keys}
        for sample in request.samples:
            for key in keys:
                value = sample.numeric_features.get(key)
                if value is not None:
                    values[key].append(float(value))
        return {
            key: round(mean(values[key]) if values[key] else 0.0, 6) for key in keys
        }

    def _estimate_outlier_limits(
        self, request: PreprocessRequest, keys: list[str]
    ) -> dict[str, tuple[float, float]]:
        limits: dict[str, tuple[float, float]] = {}
        imputations = self._calculate_numeric_imputations(request, keys)
        for key in keys:
            collected = []
            for sample in request.samples:
                value = sample.numeric_features.get(key)
                collected.append(float(imputations[key] if value is None else value))
            if not collected:
                limits[key] = (0.0, 0.0)
                continue
            values = sorted(collected)
            q1 = values[len(values) // 4]
            q3 = values[(len(values) * 3) // 4]
            iqr = q3 - q1
            lower = q1 - (1.5 * iqr)
            upper = q3 + (1.5 * iqr)
            if len(values) <= 4 and len(values) > 1:
                second_highest = values[-2]
                second_lowest = values[1] if len(values) > 2 else values[0]
                if second_highest > 0 and values[-1] / second_highest >= 5:
                    upper = second_highest * 1.5
                if values[0] > 0 and second_lowest / values[0] >= 5:
                    lower = values[0] / 1.5
            limits[key] = (lower, upper)
        return limits
