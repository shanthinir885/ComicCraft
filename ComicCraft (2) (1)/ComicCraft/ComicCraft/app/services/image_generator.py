"""Panel illustration service with a pluggable provider abstraction.
 
Providers
---------
``stable_diffusion``  Local Hugging Face Diffusers pipeline (default, per spec).
``huggingface_api``   Hosted Hugging Face Inference API (no local GPU needed).
``gemini_image``      Google Gemini image model, using your GEMINI_API_KEY.
``placeholder``       Explicit opt-in offline provider that renders a typographic
                      panel card. It is never selected silently.
"""
 
from __future__ import annotations
 
import base64
import io
import logging
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
 
from app.config import settings
from app.utils.helpers import ensure_within, sanitize_filename, unique_filename
 
logger = logging.getLogger("comiccraft.images")
 
_PIPELINE_LOCK = threading.Lock()
_PIPELINE = None
 
 
class ImageGenerationError(RuntimeError):
    """Raised when an illustration cannot be produced."""
 
 
class ImageGenerator(ABC):
    """Provider interface: turn an image prompt into a saved PNG path."""
 
    name: str = "base"
 
    @abstractmethod
    def generate(self, prompt: str, filename: Optional[str] = None) -> Path:
        """Generate an image for *prompt* and return the saved file path."""
 
    def _target_path(self, prompt: str, filename: Optional[str]) -> Path:
        """Resolve a safe destination inside static/panels."""
        name = sanitize_filename(filename) + ".png" if filename else unique_filename(prompt, "png")
        if filename and not name.lower().endswith(".png"):
            name = f"{name}.png"
        return ensure_within(settings.PANELS_DIR, settings.PANELS_DIR / name)
 
    @staticmethod
    def _style_prompt(prompt: str) -> str:
        """Append quality modifiers shared by every provider."""
        return (
            f"{prompt}, comic book illustration, clean line art, dynamic composition, "
            "vibrant colors, high detail, no text, no watermark"
        )
 
 
class StableDiffusionGenerator(ImageGenerator):
    """Local Stable Diffusion pipeline via Hugging Face Diffusers."""
 
    name = "stable_diffusion"
 
    def _load_pipeline(self):
        """Load and cache the diffusion pipeline (thread-safe, lazy)."""
        global _PIPELINE
        if _PIPELINE is not None:
            return _PIPELINE
 
        with _PIPELINE_LOCK:
            if _PIPELINE is not None:
                return _PIPELINE
            try:
                import torch  # type: ignore
                from diffusers import StableDiffusionPipeline  # type: ignore
            except ImportError as exc:
                raise ImageGenerationError(
                    "Local image generation requires 'torch' and 'diffusers'. "
                    "Install them, or set IMAGE_PROVIDER=huggingface_api in your .env."
                ) from exc
 
            if settings.IMAGE_DEVICE == "auto":
                device = "cuda" if torch.cuda.is_available() else "cpu"
            else:
                device = settings.IMAGE_DEVICE
 
            dtype = torch.float16 if device == "cuda" else torch.float32
            logger.info(
                "Loading %s on %s (this can take several minutes on first run)",
                settings.IMAGE_MODEL,
                device,
            )
            try:
                pipeline = StableDiffusionPipeline.from_pretrained(
                    settings.IMAGE_MODEL,
                    torch_dtype=dtype,
                    safety_checker=None,
                    token=settings.HF_API_KEY or None,
                )
                pipeline = pipeline.to(device)
                pipeline.set_progress_bar_config(disable=True)
            except Exception as exc:  # noqa: BLE001
                raise ImageGenerationError(
                    "Stable Diffusion could not be loaded. This usually means the model "
                    "download failed or there is not enough memory on this machine. "
                    "Set IMAGE_PROVIDER=huggingface_api to generate images in the cloud instead."
                ) from exc
 
            _PIPELINE = pipeline
            return _PIPELINE
 
    def generate(self, prompt: str, filename: Optional[str] = None) -> Path:
        pipeline = self._load_pipeline()
        path = self._target_path(prompt, filename)
        try:
            result = pipeline(
                self._style_prompt(prompt),
                num_inference_steps=settings.IMAGE_STEPS,
                guidance_scale=settings.IMAGE_GUIDANCE_SCALE,
                width=settings.IMAGE_WIDTH,
                height=settings.IMAGE_HEIGHT,
            )
            image = result.images[0]
        except Exception as exc:  # noqa: BLE001
            logger.exception("Stable Diffusion inference failed")
            raise ImageGenerationError("The illustration engine failed while drawing this panel.") from exc
 
        image.save(path)
        return path
 
 
class HuggingFaceAPIGenerator(ImageGenerator):
    """Hosted Hugging Face Inference Providers (no local GPU required).
 
    Uses the official ``huggingface_hub`` client, which routes the request to
    whichever provider currently serves the chosen model (for example FLUX.1).
    """
 
    name = "huggingface_api"
 
    @staticmethod
    def _status_code(exc: Exception) -> Optional[int]:
        response = getattr(exc, "response", None)
        return getattr(response, "status_code", None)
 
    def generate(self, prompt: str, filename: Optional[str] = None) -> Path:
        if not settings.HF_API_KEY:
            raise ImageGenerationError(
                "HF_API_KEY is not set. Add your Hugging Face token to .env to use the hosted provider."
            )
        try:
            from huggingface_hub import InferenceClient  # type: ignore
        except ImportError as exc:
            raise ImageGenerationError(
                "The hosted provider requires 'huggingface_hub'. "
                'Run: pip install -U "huggingface_hub>=0.34"'
            ) from exc
 
        client = InferenceClient(provider="auto", api_key=settings.HF_API_KEY, timeout=180)
        styled = self._style_prompt(prompt)
 
        try:
            try:
                image = client.text_to_image(
                    styled,
                    model=settings.IMAGE_MODEL,
                    width=settings.IMAGE_WIDTH,
                    height=settings.IMAGE_HEIGHT,
                )
            except Exception as size_exc:  # noqa: BLE001
                # Some providers reject custom sizes; retry once with defaults,
                # unless the failure is clearly about credentials or credits.
                if self._status_code(size_exc) in (401, 402, 403, 404, 429):
                    raise
                logger.warning("Image request with size failed (%s); retrying without size", size_exc)
                image = client.text_to_image(styled, model=settings.IMAGE_MODEL)
        except Exception as exc:  # noqa: BLE001
            status = self._status_code(exc)
            logger.exception("Hugging Face image request failed (status=%s)", status)
            if status == 401:
                raise ImageGenerationError(
                    "Your Hugging Face token was rejected. Check HF_API_KEY."
                ) from exc
            if status == 402:
                raise ImageGenerationError(
                    "Your free Hugging Face credits for this month are used up. "
                    "Wait for the monthly reset, or add credits/upgrade on huggingface.co."
                ) from exc
            if status == 403:
                raise ImageGenerationError(
                    "Your Hugging Face token cannot call Inference Providers. Create a new token "
                    "with the 'Make calls to Inference Providers' permission."
                ) from exc
            if status == 404:
                raise ImageGenerationError(
                    f"The model '{settings.IMAGE_MODEL}' is not available on Inference Providers. "
                    "Try IMAGE_MODEL=black-forest-labs/FLUX.1-schnell."
                ) from exc
            if status == 429:
                raise ImageGenerationError(
                    "Hugging Face is rate limiting requests. Wait a minute and try again."
                ) from exc
            raise ImageGenerationError(
                "The Hugging Face image service failed for this panel. Please try again."
            ) from exc
 
        try:
            image = image.convert("RGB")
        except Exception as exc:  # noqa: BLE001
            raise ImageGenerationError("The hosted image service returned unreadable data.") from exc
 
        path = self._target_path(prompt, filename)
        image.save(path)
        return path
 
 
class GeminiImageGenerator(ImageGenerator):
    """Google Gemini image generation via the REST API (uses GEMINI_API_KEY)."""
 
    name = "gemini_image"
    endpoint = "https://generativelanguage.googleapis.com/v1beta/{model}:generateContent"
 
    def generate(self, prompt: str, filename: Optional[str] = None) -> Path:
        if not settings.GEMINI_API_KEY:
            raise ImageGenerationError(
                "GEMINI_API_KEY is not set. Add it to your .env file to use Gemini image generation."
            )
        try:
            import requests  # type: ignore
            from PIL import Image  # type: ignore
        except ImportError as exc:
            raise ImageGenerationError(
                "Gemini images require 'requests' and 'Pillow'. Run: pip install -r requirements.txt"
            ) from exc
 
        model = settings.GEMINI_IMAGE_MODEL
        if not model.startswith("models/"):
            model = f"models/{model}"
        url = self.endpoint.format(model=model)
        body = {
            "contents": [{"parts": [{"text": self._style_prompt(prompt)}]}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
        }
 
        try:
            response = requests.post(
                url,
                headers={
                    "x-goog-api-key": settings.GEMINI_API_KEY,
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=180,
            )
        except Exception as exc:  # noqa: BLE001
            raise ImageGenerationError("Could not reach the Gemini image service.") from exc
 
        if response.status_code in (400, 401, 403):
            logger.error("Gemini image error %s: %s", response.status_code, response.text[:500])
            raise ImageGenerationError(
                "Gemini rejected the image request. Check GEMINI_API_KEY and that your key "
                "has access to the image model set in GEMINI_IMAGE_MODEL."
            )
        if response.status_code == 404:
            raise ImageGenerationError(
                f"The image model '{model}' is not available for this API key. "
                "Change GEMINI_IMAGE_MODEL in your .env."
            )
        if response.status_code == 429:
            logger.error("Gemini image quota: %s", response.text[:500])
            raise ImageGenerationError(
                "Gemini image quota reached (image generation may need billing enabled). "
                "Wait a minute or check your plan in Google AI Studio."
            )
        if response.status_code >= 400:
            logger.error("Gemini image error %s: %s", response.status_code, response.text[:500])
            raise ImageGenerationError("The Gemini image service returned an error for this panel.")
 
        image_bytes = None
        try:
            data = response.json()
            for candidate in data.get("candidates", []):
                for part in (candidate.get("content") or {}).get("parts", []):
                    inline = part.get("inlineData") or part.get("inline_data")
                    if inline and inline.get("data"):
                        image_bytes = base64.b64decode(inline["data"])
                        break
                if image_bytes:
                    break
        except Exception as exc:  # noqa: BLE001
            raise ImageGenerationError("The Gemini image service returned unreadable data.") from exc
 
        if not image_bytes:
            logger.error("Gemini returned no image: %s", response.text[:500])
            raise ImageGenerationError(
                "Gemini did not return an image for this panel (it may have been blocked). Please try again."
            )
 
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as exc:  # noqa: BLE001
            raise ImageGenerationError("The Gemini image data could not be read.") from exc
 
        path = self._target_path(prompt, filename)
        image.save(path)
        return path
 
 
class PlaceholderGenerator(ImageGenerator):
    """Offline typographic panel card. Explicit opt-in only (IMAGE_PROVIDER=placeholder)."""
 
    name = "placeholder"
 
    def generate(self, prompt: str, filename: Optional[str] = None) -> Path:
        try:
            from PIL import Image, ImageDraw  # type: ignore
        except ImportError as exc:
            raise ImageGenerationError("Pillow is required for the placeholder provider.") from exc
 
        width, height = settings.IMAGE_WIDTH, settings.IMAGE_HEIGHT
        image = Image.new("RGB", (width, height), (17, 17, 31))
        draw = ImageDraw.Draw(image)
 
        for index in range(0, height, 6):
            shade = 24 + int(28 * (index / max(height, 1)))
            draw.line([(0, index), (width, index)], fill=(shade, shade, shade + 26))
 
        draw.rectangle([12, 12, width - 12, height - 12], outline=(124, 92, 255), width=4)
        draw.text((28, 28), "COMICCRAFT · PLACEHOLDER PANEL", fill=(76, 201, 240))
 
        words = prompt.split()
        lines, current = [], ""
        for word in words:
            if len(current) + len(word) + 1 > 42:
                lines.append(current)
                current = word
            else:
                current = f"{current} {word}".strip()
        if current:
            lines.append(current)
 
        y = 80
        for line in lines[:14]:
            draw.text((28, y), line, fill=(226, 226, 240))
            y += 22
 
        path = self._target_path(prompt, filename)
        image.save(path)
        return path
 
 
_PROVIDERS = {
    StableDiffusionGenerator.name: StableDiffusionGenerator,
    HuggingFaceAPIGenerator.name: HuggingFaceAPIGenerator,
    GeminiImageGenerator.name: GeminiImageGenerator,
    PlaceholderGenerator.name: PlaceholderGenerator,
}
 
 
def get_generator(provider: Optional[str] = None) -> ImageGenerator:
    """Return the configured image generator instance."""
    key = (provider or settings.IMAGE_PROVIDER).strip().lower()
    generator_class = _PROVIDERS.get(key)
    if generator_class is None:
        raise ImageGenerationError(
            f"Unknown IMAGE_PROVIDER '{key}'. Valid options: {', '.join(sorted(_PROVIDERS))}."
        )
    return generator_class()
 
 
def generate_image(prompt: str, filename: Optional[str] = None) -> Path:
    """Generate one panel illustration and return its saved path."""
    if not prompt or not prompt.strip():
        raise ImageGenerationError("An empty image prompt cannot be illustrated.")
    return get_generator().generate(prompt.strip(), filename)
