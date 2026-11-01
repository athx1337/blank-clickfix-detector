from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator

Verdict = Literal["suspicious", "uncertain", "no_suspicious_signals"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Context(StrictModel):
    inside_dialog: StrictBool = False
    has_code: StrictBool = False
    has_copy_button: StrictBool = False


class Block(StrictModel):
    block_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    text: str = Field(min_length=1, max_length=2000)
    context: Context = Field(default_factory=Context)


class Extraction(StrictModel):
    truncated: StrictBool = False
    main_frame_only: StrictBool = True
    visited_nodes: int = Field(default=0, ge=0, le=6000)


class AnalyzeRequest(StrictModel):
    scan_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    blocks: list[Block] = Field(max_length=24)
    extraction: Extraction = Field(default_factory=Extraction)
    clipboard: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def bounded_unique(self):
        if len({b.block_id for b in self.blocks}) != len(self.blocks):
            raise ValueError("duplicate block IDs")
        if sum(len(b.text) for b in self.blocks) > 24000:
            raise ValueError("total text limit exceeded")
        return self


class Finding(StrictModel):
    code: str
    message: str
    block_id: str
    evidence: str


class AnalyzeResponse(StrictModel):
    scan_id: str
    verdict: Verdict
    detector_mode: Literal["rules_only", "hybrid"]
    findings: list[Finding]
    model_version: str | None
    model_scores: dict[str, float] | None = None
    processing_ms: float
    block_count: int
    extraction: Extraction
