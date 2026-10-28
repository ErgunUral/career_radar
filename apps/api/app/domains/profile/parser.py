from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from pypdf import PdfReader

from ..matching.schemas import CandidateProfileInput, WorkMode

SKILL_KEYWORDS = [
    "python",
    "jira",
    "xray",
    "ci/cd",
    "selenium",
    "playwright",
    "postman",
    "api testing",
    "agile",
    "scrum",
    "test automation",
    "quality assurance",
    "qa",
    "fintech",
    "payment systems",
    "cypress",
    "jenkins",
    "github actions",
    "gitlab ci/cd",
    "microservice",
]

CERTIFICATION_KEYWORDS = ["istqb", "pmp", "psm", "cspo", "scrum master"]
EDUCATION_KEYWORDS = [
    "computer engineering",
    "software engineering",
    "bilgisayar mühendisliği",
    "elektronik",
    "management information systems",
]
INDUSTRY_KEYWORDS = ["fintech", "e-commerce", "e-ticaret", "payment", "banking", "saas"]
LANGUAGE_KEYWORDS = ["ingilizce", "english", "turkce", "turkish", "almanca", "german"]
TITLE_KEYWORDS = [
    "test manager",
    "software test manager",
    "qa manager",
    "qa team lead",
    "test team lead",
    "head of qa",
    "quality engineering manager",
    "software quality assurance manager",
    "test automation manager",
    "senior test manager",
    "qa lead",
    "lead qa analyst",
]
LOCATION_KEYWORDS = [
    "istanbul",
    "ankara",
    "izmir",
    "remote",
    "hybrid",
    "london",
    "berlin",
    "amsterdam",
]
MANAGEMENT_ROLE_KEYWORDS = [
    "manager",
    "lead",
    "head",
    "lider",
    "yonet",
    "test takim lideri",
    "qa team lead",
]
MONTH_ALIASES = {
    "ocak": 1,
    "january": 1,
    "jan": 1,
    "subat": 2,
    "şubat": 2,
    "february": 2,
    "feb": 2,
    "mart": 3,
    "march": 3,
    "mar": 3,
    "nisan": 4,
    "april": 4,
    "apr": 4,
    "mayis": 5,
    "mayıs": 5,
    "may": 5,
    "haziran": 6,
    "june": 6,
    "jun": 6,
    "temmuz": 7,
    "july": 7,
    "jul": 7,
    "agustos": 8,
    "ağustos": 8,
    "august": 8,
    "aug": 8,
    "eylul": 9,
    "eylül": 9,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "ekim": 10,
    "october": 10,
    "oct": 10,
    "kasim": 11,
    "kasım": 11,
    "november": 11,
    "nov": 11,
    "aralik": 12,
    "aralık": 12,
    "december": 12,
    "dec": 12,
}
MONTH_PATTERN = "|".join(sorted(MONTH_ALIASES, key=len, reverse=True))


class CvParser:
    def extract_text(self, file_path: str) -> str:
        path = Path(file_path)
        suffix = path.suffix.casefold()
        if suffix == ".pdf":
            return self._extract_pdf_text(path)
        if suffix == ".docx":
            return self._extract_docx_text(path)
        raise ValueError(
            "Desteklenmeyen CV formatı. Yalnızca PDF ve DOCX kabul edilir."
        )

    def parse_candidate_profile(
        self, text: str, candidate_id: str
    ) -> tuple[CandidateProfileInput, str, list[str]]:
        normalized = self._normalize(text)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        headline = self._extract_headline(lines, normalized)
        summary = self._build_summary(lines)
        total_experience_years = self._extract_years(
            normalized, r"(\d{1,2})(?:\+)?\s*(?:yil|year)"
        )
        management_years = self._extract_management_years(normalized, lines)
        team_size = self._extract_team_size(normalized)
        skills = self._collect_keywords(normalized, SKILL_KEYWORDS)
        certifications = self._collect_keywords(normalized, CERTIFICATION_KEYWORDS)
        educations = self._collect_keywords(normalized, EDUCATION_KEYWORDS)
        industries = self._collect_keywords(normalized, INDUSTRY_KEYWORDS)
        languages = self._collect_keywords(normalized, LANGUAGE_KEYWORDS)
        preferred_locations = self._collect_keywords(normalized, LOCATION_KEYWORDS)
        target_positions = self._collect_keywords(
            normalized, TITLE_KEYWORDS
        ) or self._infer_target_positions(headline)
        work_modes = self._infer_work_modes(normalized)
        profile = CandidateProfileInput(
            candidate_id=candidate_id,
            headline=headline,
            summary=summary,
            total_experience_years=total_experience_years,
            management_years=management_years,
            team_size_managed=team_size,
            skills=self._titleize_items(skills),
            industries=self._titleize_items(industries),
            languages=self._titleize_items(languages),
            certifications=[
                item.upper() if item.lower() == "istqb" else item.title()
                for item in certifications
            ],
            educations=self._titleize_items(educations),
            preferred_locations=self._titleize_items(preferred_locations),
            work_modes=work_modes,
            raw_text=text,
        )
        professional_summary = self._build_professional_summary(profile)
        return profile, professional_summary, self._titleize_items(target_positions)

    def _extract_pdf_text(self, path: Path) -> str:
        reader = PdfReader(str(path))
        return "\n".join(
            (page.extract_text() or "").strip() for page in reader.pages
        ).strip()

    def _extract_docx_text(self, path: Path) -> str:
        document = Document(str(path))
        lines = [
            paragraph.text.strip()
            for paragraph in document.paragraphs
            if paragraph.text.strip()
        ]
        return "\n".join(lines)

    def _normalize(self, text: str) -> str:
        lowered = unicodedata.normalize("NFKD", text.casefold())
        lowered = "".join(char for char in lowered if not unicodedata.combining(char))
        lowered = lowered.translate(
            str.maketrans({"ı": "i", "–": "-", "—": "-"})  # type: ignore[arg-type]
        )
        lowered = re.sub(r"[^\w\s/+.-]", " ", lowered)
        lowered = re.sub(r"\s+", " ", lowered)
        return lowered.strip()

    def _extract_headline(self, lines: list[str], normalized: str) -> str:
        if lines:
            first_line = lines[0].strip()
            if self._looks_like_name(first_line) and len(lines) > 1:
                second_line = lines[1].strip()
                if self._has_role_signal(second_line):
                    return second_line[:120]
            if 3 <= len(first_line) <= 120:
                return first_line
        detected = self._collect_keywords(normalized, TITLE_KEYWORDS)
        return self._titleize_items([detected[0]])[0] if detected else "Aday Profili"

    def _build_summary(self, lines: list[str]) -> str:
        summary_lines: list[str] = []
        for line in lines[1:6]:
            if len(" ".join(summary_lines + [line])) > 280:
                break
            summary_lines.append(line)
        return (
            " ".join(summary_lines)[:280]
            if summary_lines
            else (lines[0][:280] if lines else "")
        )

    def _extract_years(self, normalized: str, pattern: str) -> float:
        matches = [float(match) for match in re.findall(pattern, normalized)]
        return max(matches) if matches else 0.0

    def _extract_management_years(self, normalized: str, lines: list[str]) -> float:
        direct_years = max(
            self._extract_years(
                normalized,
                r"(\d{1,2})(?:\+)?\s*(?:yil|year).{0,50}(?:yonetim|yonetici|yonet|muduru|mudur|manager|management|lead|lider|testing quality assurance and test management)",
            ),
            self._extract_years(
                normalized,
                r"(?:yonetim|yonetici|yonet|muduru|mudur|manager|management|lead|lider).{0,50}(\d{1,2})(?:\+)?\s*(?:yil|year)",
            ),
            self._extract_years(
                normalized,
                r"(\d{1,2})(?:\+)?\s*(?:yil|year).{0,20}(?:takim|ekip|team).{0,25}(?:yonet|lead|manager|mudur)",
            ),
            self._extract_years(
                normalized, r"(\d{1,2})(?:\+)?\s*(?:yil|year).{0,15}(?:management lead)"
            ),
        )
        derived_years = self._extract_management_years_from_roles(lines)
        if direct_years == 0 and derived_years < 2:
            mgmt_role_patterns = (
                "test yoneticisi",
                "test manager",
                "kalite guvence müdürü",
                "quality assurance manager",
                "qa manager",
                "qa team lead",
                "test team lead",
                "head of qa",
                "muduru",
                "müdür",
                "team lead",
                "takım lideri",
                "quality engineering manager",
                "software quality assurance manager",
            )
            total_exp = self._extract_years(
                normalized, r"(\d{1,2})(?:\+)?\s*(?:yil|year)"
            )
            if total_exp > 0 and any(
                self._normalize(p) in normalized for p in mgmt_role_patterns
            ):
                fallback = round(total_exp * 0.6, 1)
                return max(direct_years, derived_years, fallback)
        return round(max(direct_years, derived_years), 1)

    def _extract_team_size(self, normalized: str) -> int:
        match = re.search(
            r"(\d{1,4})\s*(?:kisilik|person|people|member|uye)", normalized
        )
        return int(match.group(1)) if match else 0

    def _collect_keywords(self, normalized: str, keywords: list[str]) -> list[str]:
        return [
            keyword for keyword in keywords if self._normalize(keyword) in normalized
        ]

    def _infer_target_positions(self, headline: str) -> list[str]:
        headline_cf = headline.casefold()
        matches = [keyword for keyword in TITLE_KEYWORDS if keyword in headline_cf]
        return (
            matches or ["qa manager"] if self._has_role_signal(headline) else [headline]
        )

    def _infer_work_modes(self, normalized: str) -> list[WorkMode]:
        modes: list[WorkMode] = []
        if "remote" in normalized or "uzaktan" in normalized:
            modes.append(WorkMode.remote)
        if "hybrid" in normalized or "hibrit" in normalized:
            modes.append(WorkMode.hybrid)
        if "onsite" in normalized or "office" in normalized or "ofis" in normalized:
            modes.append(WorkMode.onsite)
        return modes or [WorkMode.remote]

    def _build_professional_summary(self, profile: CandidateProfileInput) -> str:
        skill_text = (
            ", ".join(profile.skills[:5]) if profile.skills else "genel kalite yönetimi"
        )
        industry_text = (
            ", ".join(profile.industries[:2]) if profile.industries else "teknoloji"
        )
        return (
            f"{profile.headline} profili, {profile.total_experience_years:.0f}+ yıl deneyim, "
            f"{profile.management_years:.0f}+ yıl yönetim geçmişi ve {industry_text} odağı ile "
            f"{skill_text} yetkinliklerini öne çıkarıyor."
        )

    def _titleize_items(self, items: list[str]) -> list[str]:
        normalized: list[str] = []
        for item in items:
            if item.upper() in {"QA", "CI/CD"}:
                normalized.append(item.upper())
            elif item.lower() == "xray":
                normalized.append("Xray")
            elif item.lower() in {"english", "ingilizce"}:
                normalized.append("English")
            elif item.lower() in {"turkish", "turkce"}:
                normalized.append("Türkçe")
            elif item.lower() == "german":
                normalized.append("German")
            elif item.lower() == "almanca":
                normalized.append("Almanca")
            else:
                normalized.append(item.title())
        return normalized

    def _looks_like_name(self, line: str) -> bool:
        tokens = [token for token in re.split(r"\s+", line.strip()) if token]
        if not 2 <= len(tokens) <= 4:
            return False
        if any(any(char.isdigit() for char in token) for token in tokens):
            return False
        return all(re.fullmatch(r"[A-Za-zÇĞİÖŞÜçğıöşü.-]+", token) for token in tokens)

    def _has_role_signal(self, text: str) -> bool:
        normalized = self._normalize(text)
        return any(
            keyword in normalized
            for keyword in TITLE_KEYWORDS + MANAGEMENT_ROLE_KEYWORDS
        )

    def _extract_management_years_from_roles(self, lines: list[str]) -> float:
        intervals: list[tuple[int, int]] = []
        for index, line in enumerate(lines):
            candidate_segments = [line]
            if index + 1 < len(lines):
                candidate_segments.append(f"{line} {lines[index + 1]}")
            for segment in candidate_segments:
                normalized_segment = self._normalize(segment)
                if not any(
                    keyword in normalized_segment
                    for keyword in MANAGEMENT_ROLE_KEYWORDS
                ):
                    continue
                for match in re.finditer(
                    rf"(?P<start_month>{MONTH_PATTERN})\s+(?P<start_year>\d{{4}})\s*[–-]\s*(?:(?P<end_month>{MONTH_PATTERN})\s+(?P<end_year>\d{{4}})|(?P<present>devam|present|current|now))",
                    normalized_segment,
                ):
                    start = self._month_index(
                        match.group("start_year"), match.group("start_month")
                    )
                    if match.group("present"):
                        now = datetime.now(timezone.utc)
                        end = (now.year * 12) + now.month
                    else:
                        end = self._month_index(
                            match.group("end_year"), match.group("end_month")
                        )
                    intervals.append((start, end))

        if not intervals:
            return 0.0

        merged: list[tuple[int, int]] = []
        for start, end in sorted(intervals):
            if not merged or start > merged[-1][1] + 1:
                merged.append((start, end))
            else:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))

        total_months = sum(max((end - start) + 1, 0) for start, end in merged)
        return total_months / 12

    def _month_index(self, year: str, month: str) -> int:
        return (int(year) * 12) + MONTH_ALIASES[month]
