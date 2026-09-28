"""PDF export for a finished comic, built with FPDF."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.utils.helpers import ensure_within, sanitize_filename, unique_filename

logger = logging.getLogger("comiccraft.export")

PAGE_MARGIN = 15
TITLE_COLOR = (124, 92, 255)
ACCENT_COLOR = (76, 201, 240)
TEXT_COLOR = (28, 28, 40)
MUTED_COLOR = (110, 110, 130)


class PDFExportError(RuntimeError):
    """Raised when the comic PDF cannot be produced."""


def _import_fpdf():
    """Import FPDF lazily and surface a friendly error if it is missing."""
    try:
        from fpdf import FPDF  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise PDFExportError(
            "The 'fpdf2' package is not installed. Run: pip install -r requirements.txt"
        ) from exc
    return FPDF


def _latin1(text: str) -> str:
    """Make text safe for the built-in core fonts used by FPDF."""
    replacements = {
        "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
        "\u2013": "-", "\u2014": "-", "\u2026": "...", "\u00a0": " ",
    }
    cleaned = str(text or "")
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)
    return cleaned.encode("latin-1", "replace").decode("latin-1")


def _image_box(image_path: str, max_width: float, max_height: float) -> tuple[float, float]:
    """Return width/height that fit inside the box without distorting aspect ratio."""
    try:
        from PIL import Image  # type: ignore

        with Image.open(image_path) as image:
            width, height = image.size
    except Exception:  # noqa: BLE001 - fall back to a square box
        width, height = 1, 1

    ratio = min(max_width / width, max_height / height)
    return width * ratio, height * ratio


def save_pdf(
    layout: List[Dict[str, Any]],
    title: str = "ComicCraft Comic",
    metadata: Optional[Dict[str, str]] = None,
) -> Path:
    """Compile the comic into a multi-page PDF under ``static/exports``.

    Args:
        layout: Panel dicts produced by ``build_comic_layout``.
        title: Comic title printed on the cover and page headers.
        metadata: Optional character/setting/tone/art-style context for the cover.

    Returns:
        Absolute path to the written PDF.

    Raises:
        PDFExportError: When FPDF is unavailable or writing fails.
    """
    if not layout:
        raise PDFExportError("There are no panels to export.")

    FPDF = _import_fpdf()
    meta = metadata or {}
    safe_title = _latin1(title)

    class ComicPDF(FPDF):  # noqa: D401 - small internal subclass
        """FPDF subclass adding a running header and page numbers."""

        def header(self) -> None:
            if self.page_no() == 1:
                return
            self.set_font("Helvetica", "B", 9)
            self.set_text_color(*MUTED_COLOR)
            self.cell(0, 8, safe_title, new_x="LMARGIN", new_y="NEXT", align="L")
            self.set_draw_color(220, 220, 230)
            self.line(PAGE_MARGIN, 22, self.w - PAGE_MARGIN, 22)
            self.ln(4)

        def footer(self) -> None:
            self.set_y(-14)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(*MUTED_COLOR)
            self.cell(0, 8, f"ComicCraft  |  Page {self.page_no()}", align="C")

    pdf = ComicPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
    pdf.set_title(safe_title)
    pdf.set_author("ComicCraft")

    usable_width = pdf.w - (2 * PAGE_MARGIN)

    # ---- Cover page ---------------------------------------------------
    pdf.add_page()
    pdf.ln(50)
    pdf.set_font("Helvetica", "B", 30)
    pdf.set_text_color(*TITLE_COLOR)
    pdf.multi_cell(usable_width, 14, safe_title, align="C")
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(*MUTED_COLOR)
    pdf.multi_cell(usable_width, 8, "An AI-generated comic created with ComicCraft", align="C")
    pdf.ln(10)

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*TEXT_COLOR)
    for label, key in (
        ("Main character", "character_name"),
        ("Setting", "setting"),
        ("Tone", "tone"),
        ("Art style", "art_style"),
    ):
        value = meta.get(key)
        if value:
            pdf.multi_cell(usable_width, 7, _latin1(f"{label}: {value}"), align="C")
    pdf.ln(6)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED_COLOR)
    pdf.multi_cell(usable_width, 6, _latin1(f"{len(layout)} panels"), align="C")

    # ---- Panel pages ---------------------------------------------------
    for panel in layout:
        pdf.add_page()

        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*ACCENT_COLOR)
        pdf.cell(0, 6, _latin1(f"PANEL {int(panel.get('panel_number', 0)):02d}"),
                 new_x="LMARGIN", new_y="NEXT")

        pdf.set_font("Helvetica", "B", 17)
        pdf.set_text_color(*TITLE_COLOR)
        pdf.multi_cell(usable_width, 9, _latin1(panel.get("title", "")))
        pdf.ln(2)

        image_path = panel.get("image_path")
        if image_path and Path(image_path).exists():
            box_width, box_height = _image_box(image_path, usable_width, 110)
            x_offset = PAGE_MARGIN + (usable_width - box_width) / 2
            try:
                pdf.image(image_path, x=x_offset, y=pdf.get_y(), w=box_width, h=box_height)
                pdf.set_y(pdf.get_y() + box_height + 6)
            except Exception:  # noqa: BLE001
                logger.warning("Could not embed image for panel %s", panel.get("panel_number"))
                pdf.set_font("Helvetica", "I", 10)
                pdf.set_text_color(*MUTED_COLOR)
                pdf.multi_cell(usable_width, 6, "Illustration unavailable for this panel.")
        else:
            pdf.set_font("Helvetica", "I", 10)
            pdf.set_text_color(*MUTED_COLOR)
            pdf.multi_cell(usable_width, 6, "Illustration unavailable for this panel.")
            pdf.ln(2)

        sections = (
            ("SCENE", panel.get("scene_description", ""), "I"),
            ("CAPTION", panel.get("caption", ""), ""),
            ("NARRATION", panel.get("narration", ""), ""),
        )
        for label, value, style in sections:
            if not value:
                continue
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*MUTED_COLOR)
            pdf.cell(0, 5, label, new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", style, 11)
            pdf.set_text_color(*TEXT_COLOR)
            pdf.multi_cell(usable_width, 6, _latin1(value))
            pdf.ln(2)

        dialogue = panel.get("dialogue") or []
        if dialogue:
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*MUTED_COLOR)
            pdf.cell(0, 5, "DIALOGUE", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 11)
            pdf.set_text_color(*TEXT_COLOR)
            for line in dialogue:
                pdf.multi_cell(usable_width, 6, _latin1(f"\u2022 {line}"))

    filename = unique_filename(sanitize_filename(title or "comic"), "pdf")
    pdf_path = ensure_within(settings.EXPORTS_DIR, settings.EXPORTS_DIR / filename)

    try:
        pdf.output(str(pdf_path))
    except Exception as exc:  # noqa: BLE001
        logger.exception("PDF write failed")
        raise PDFExportError("We could not write your comic PDF. Please try again.") from exc

    return pdf_path
