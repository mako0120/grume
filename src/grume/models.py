from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EmailJob(BaseModel):
    message_id: str
    thread_id: str | None = None
    sender: str
    subject: str
    store_name: str
    course_name: str | None = None
    area: str | None = None
    dishes: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    image_paths: list[str] = Field(default_factory=list)


class ImagePlanItem(BaseModel):
    filename: str
    page_index: int
    role: Literal[
        "cover", "exterior", "interior", "drink", "menu",
        "dish", "grilling", "closeup", "summary"
    ]
    dish_name: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    visual_note: str = ""


class ImagePlan(BaseModel):
    items: list[ImagePlanItem]
    needs_review: bool = False
    review_reason: str | None = None


class ResearchSource(BaseModel):
    label: str
    url: str | None = None


class ResearchedStore(BaseModel):
    official_name: str
    address: str | None = None
    nearest_station: str | None = None
    area: str | None = None
    instagram: str | None = None
    genre: str | None = None
    strengths: list[str] = Field(default_factory=list)
    verified_facts: list[str] = Field(default_factory=list)
    caution_notes: list[str] = Field(default_factory=list)
    sources: list[ResearchSource] = Field(default_factory=list)


class PageCopy(BaseModel):
    page_index: int
    filename: str
    dish_name: str | None = None
    text: str


class PostPackage(BaseModel):
    design_title: str
    store_name: str
    area: str
    nearest_station: str | None = None
    cover_subcopy: str
    cover_hook: str
    pages: list[PageCopy]
    needs_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)
