from typing import Literal

from pydantic import BaseModel, Field


class Rule(BaseModel):
    label: str
    weight: int
    observed: bool | None
    action: str


class Preview(BaseModel):
    repository: str
    commit: str
    files: list[str]
    bytes: int
    score: int | None
    rules: list[Rule]
    limitations: list[str]


class Finding(BaseModel):
    title: str
    severity: Literal["critical", "high", "medium", "low"]
    category: str
    file: str
    line: int | None = None
    evidence: str = Field(min_length=1)
    description: str
    recommendation: str
    difficulty: Literal["easy", "moderate", "hard"]
    benefit: str
    verification: str
    confidence: Literal["low", "medium", "high"]


class Review(BaseModel):
    summary: str = Field(min_length=1)
    findings: list[Finding]
    strengths: list[str]
    limitations: list[str]


class Report(BaseModel):
    snapshot: Preview
    review: Review
