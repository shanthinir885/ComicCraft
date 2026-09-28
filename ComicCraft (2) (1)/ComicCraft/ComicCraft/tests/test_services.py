"""Service-layer tests: validators, helpers, layout building and PDF export."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.exporters import save_pdf
from app.services.image_generator import PlaceholderGenerator
from app.services.layout_builder import build_comic_layout
from app.utils.helpers import extract_json, sanitize_filename, truncate, unique_filename
from app.utils.validators import AIOutputError, normalize_outline, normalize_story


def test_sanitize_filename_strips_unsafe_characters() -> None:
    assert sanitize_filename("A brave fox/../.. <portal>!") == "a_brave_fox_portal"
    assert sanitize_filename("") == "comiccraft"


def test_unique_filename_has_extension() -> None:
    name = unique_filename("comic title", "pdf")
    assert name.endswith(".pdf")
    assert " " not in name


def test_truncate_adds_ellipsis() -> None:
    assert truncate("one two three four", 9).endswith("…")
    assert truncate("short", 20) == "short"


def test_extract_json_handles_code_fences_and_prose() -> None:
    fenced = '```json\n{"panels": [{"panel_number": 1}]}\n```'
    assert extract_json(fenced)["panels"][0]["panel_number"] == 1

    noisy = 'Here you go!\n{"a": 1}\nHope that helps.'
    assert extract_json(noisy) == {"a": 1}

    assert extract_json("not json at all") is None


def test_normalize_outline_accepts_aliases_and_renumbers() -> None:
    payload = {
        "panels": [
            {"panel": 2, "title": "Second", "scene": "Deeper in.", "prompt": "art two"},
            {"panel": 1, "title": "First", "scene_description": "At the edge.", "image_prompt": "art one"},
        ]
    }
    panels = normalize_outline(payload, expected_panels=5)
    assert [panel["panel_number"] for panel in panels] == [1, 2]
    assert panels[0]["title"] == "First"


def test_normalize_outline_rejects_garbage() -> None:
    with pytest.raises(AIOutputError):
        normalize_outline({"panels": []})


def test_normalize_story_pads_and_formats_dialogue() -> None:
    payload = [
        {
            "panel_number": 1,
            "caption": "A hush.",
            "narration": "Finn steps forward.",
            "dialogue": [{"speaker": "FINN", "line": "Here we go."}],
        }
    ]
    story = normalize_story(payload, panel_count=3)
    assert len(story) == 3
    assert story[0]["dialogue"] == ["FINN: Here we go."]


def test_build_comic_layout_merges_sources(sample_outline, sample_story) -> None:
    images = [
        {"panel_number": index, "image_path": None, "image_url": f"/static/panels/p{index}.png", "image_error": None}
        for index in range(1, 6)
    ]
    layout = build_comic_layout(sample_outline, sample_story, images)
    assert len(layout) == 5
    assert layout[0]["caption"] == "Caption 1"
    assert layout[4]["image_url"].endswith("p5.png")


def test_placeholder_generator_writes_png() -> None:
    path = PlaceholderGenerator().generate("A fox at the edge of a glowing forest")
    assert Path(path).exists()
    assert Path(path).suffix == ".png"
    Path(path).unlink(missing_ok=True)


def test_save_pdf_creates_file(sample_outline, sample_story) -> None:
    layout = build_comic_layout(sample_outline, sample_story, None)
    pdf_path = save_pdf(layout, title="Test Comic", metadata={"character_name": "Finn"})
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 1000
    pdf_path.unlink(missing_ok=True)
