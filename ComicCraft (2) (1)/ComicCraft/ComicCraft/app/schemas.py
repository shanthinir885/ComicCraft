"""Pydantic schemas used for request validation and API responses."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.config import settings

ALLOWED_TONES = [
    "Funny",
    "Dramatic",
    "Adventure",
    "Dark",
    "Emotional",
    "Light-hearted",
    "Epic",
    "Mysterious",
]

ALLOWED_ART_STYLES = [
    "Anime",
    "Comic Book",
    "Pixel Art",
    "Cartoon",
    "Realistic",
    "Manga",
    "Fantasy",
    "Cinematic",
]

SUGGESTED_SETTINGS = [
    "Enchanted Forest",
    "Space",
    "Futuristic City",
    "School",
    "Medieval Kingdom",
    "Underwater World",
]


class PromptRequest(BaseModel):
    """Payload accepted by the JSON comic-generation endpoint."""

    story_prompt: str = Field(..., min_length=10, max_length=settings.MAX_PROMPT_LENGTH)
    character_name: str = Field(..., min_length=1, max_length=settings.MAX_NAME_LENGTH)
    setting: str = Field(..., min_length=2, max_length=settings.MAX_NAME_LENGTH)
    tone: str = Field(..., min_length=2, max_length=settings.MAX_NAME_LENGTH)
    art_style: str = Field(..., min_length=2, max_length=settings.MAX_NAME_LENGTH)

    @field_validator("story_prompt", "character_name", "setting", "tone", "art_style")
    @classmethod
    def _strip_whitespace(cls, value: str) -> str:
        cleaned = " ".join(str(value).split())
        if not cleaned:
            raise ValueError("This field cannot be empty.")
        return cleaned

    model_config = {
        "json_schema_extra": {
            "example": {
                "story_prompt": (
                    "A brave fox discovers a mysterious portal inside an "
                    "enchanted forest and must decide whether to step through."
                ),
                "character_name": "Finn",
                "setting": "Enchanted Forest",
                "tone": "Adventure",
                "art_style": "Comic Book",
            }
        }
    }


class PanelOutline(BaseModel):
    """A single panel as produced by the outline model."""

    panel_number: int = Field(..., ge=1)
    title: str
    scene_description: str
    image_prompt: str


class ComicPanel(BaseModel):
    """A fully assembled comic panel ready for rendering or export."""

    panel_number: int
    title: str
    scene_description: str
    caption: str
    narration: str
    dialogue: List[str] = Field(default_factory=list)
    image_prompt: str
    image_url: Optional[str] = None
    image_path: Optional[str] = None
    image_error: Optional[str] = None


class ComicResponse(BaseModel):
    """Successful response returned by the JSON generation endpoint."""

    success: bool = True
    title: str
    character_name: str
    setting: str
    tone: str
    art_style: str
    panels: List[ComicPanel]
    pdf_url: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """Uniform error envelope returned to API clients."""

    success: bool = False
    error: str
    code: str = "generation_error"


class ImageTestRequest(BaseModel):
    """Payload for the developer image-generation test route."""

    prompt: str = Field(
        default="A futuristic city at sunset, sci-fi, cinematic, comic book style",
        min_length=3,
        max_length=settings.MAX_PROMPT_LENGTH,
    )


class HealthResponse(BaseModel):
    """Health-probe payload."""

    status: str
    app: str
    environment: str
    gemini_configured: bool
    image_provider: str
    image_configured: bool
