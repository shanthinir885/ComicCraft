"""Shared pytest fixtures for the ComicCraft test suite."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("IMAGE_PROVIDER", "placeholder")
os.environ.setdefault("DEBUG", "true")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client() -> TestClient:
    """Return a FastAPI test client bound to the application."""
    return TestClient(app)


@pytest.fixture()
def sample_outline() -> list[dict]:
    """A minimal valid outline used by layout and export tests."""
    return [
        {
            "panel_number": index,
            "title": f"Panel {index}",
            "scene_description": f"Scene description {index}.",
            "image_prompt": f"Illustration prompt {index}.",
        }
        for index in range(1, 6)
    ]


@pytest.fixture()
def sample_story() -> list[dict]:
    """A matching story payload for the sample outline."""
    return [
        {
            "panel_number": index,
            "caption": f"Caption {index}",
            "narration": f"Narration for panel {index}.",
            "dialogue": [f"HERO: Line {index}"],
        }
        for index in range(1, 6)
    ]
