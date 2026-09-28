# ComicCraft — AI Comic Story Creator

Turn a one-line idea into a complete, illustrated comic. ComicCraft generates a structured
panel outline, writes narration/captions/dialogue, illustrates every panel, renders a comic
reader in the browser and exports a print-ready PDF.

| Layer | Technology |
| --- | --- |
| Backend | FastAPI, Uvicorn, Pydantic v2 |
| Templating | Jinja2 |
| Outline model | Gemini Flash (`GEMINI_OUTLINE_MODEL`) |
| Story model | Gemini Pro (`GEMINI_STORY_MODEL`) |
| Illustrations | Stable Diffusion via Diffusers, or the hosted Hugging Face Inference API |
| Export | FPDF (fpdf2) |
| Frontend | Mobile-first CSS + vanilla JavaScript (no frameworks) |

---

## 1. Folder structure

```text
ComicCraft/
├── app/
│   ├── __init__.py
│   ├── main.py                 # App factory, static mount, global error handling
│   ├── routes.py               # All HTTP routes
│   ├── schemas.py              # Pydantic models
│   ├── config.py               # Env-driven settings
│   ├── templating.py           # Shared Jinja2 environment
│   ├── services/
│   │   ├── __init__.py
│   │   ├── gemini_client.py    # Shared Gemini SDK wrapper
│   │   ├── gemini_flash.py     # generate_outline()
│   │   ├── gemini_pro.py       # generate_story()
│   │   ├── image_generator.py  # Provider abstraction + generate_image()
│   │   ├── layout_builder.py   # build_comic_layout(), generate_panel_images()
│   │   ├── exporters.py        # save_pdf()
│   │   └── comic_service.py    # Pipeline orchestration
│   └── utils/
│       ├── __init__.py
│       ├── validators.py       # AI output normalisation
│       └── helpers.py          # Safe paths, filenames, JSON extraction
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── comic_preview.html
│   ├── export_success.html
│   ├── error.html
│   └── partials/
│       ├── navbar.html
│       ├── footer.html
│       └── loading.html
├── static/
│   ├── css/style.css
│   ├── js/app.js
│   ├── images/
│   ├── panels/                 # Generated panel images
│   ├── exports/                # Generated PDFs
│   └── fonts/
├── tests/
│   ├── conftest.py
│   ├── test_routes.py
│   ├── test_schemas.py
│   └── test_services.py
├── .env.example
├── .gitignore
├── requirements.txt
├── run.py
└── README.md
```

---

## 2. Installation (Windows 10/11 — PowerShell)

```powershell
cd path\to\ComicCraft
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

If activation is blocked by the execution policy:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Optional: local Stable Diffusion

Only needed when `IMAGE_PROVIDER=stable_diffusion`:

```powershell
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install diffusers==0.31.0 transformers==4.46.3 accelerate==1.2.1 safetensors==0.4.5
```

CPU-only machines can run it, but a single panel may take several minutes. The first run
downloads several gigabytes of model weights. If you have no GPU, set
`IMAGE_PROVIDER=huggingface_api` instead and supply `HF_API_KEY`.

---

## 3. Environment configuration

```powershell
Copy-Item .env.example .env
notepad .env
```

| Variable | Purpose |
| --- | --- |
| `GEMINI_API_KEY` | Required. Google AI Studio key used for both text models. |
| `GEMINI_OUTLINE_MODEL` | Model used for the structured panel outline. |
| `GEMINI_STORY_MODEL` | Model used for narration and dialogue. |
| `IMAGE_PROVIDER` | `stable_diffusion`, `huggingface_api` or `placeholder`. |
| `IMAGE_MODEL` | Diffusion model id, e.g. `runwayml/stable-diffusion-v1-5`. |
| `HF_API_KEY` | Hugging Face token — required for `huggingface_api`, sometimes for gated models. |
| `PANEL_COUNT` | Panels per comic (default 5). |
| `MAX_PROMPT_LENGTH` | Server-side prompt limit, mirrored by the UI counter. |
| `DEBUG` / `APP_ENV` | Development toggles. |

Keys are read server-side only and are never sent to the browser. `.env` is gitignored.

`IMAGE_PROVIDER=placeholder` renders typographic panels for UI work. It is never selected
automatically — if Stable Diffusion cannot load, the app returns a clear configuration error
rather than silently substituting fake artwork.

---

## 4. Run the application

```powershell
uvicorn app.main:app --reload
```

or:

```powershell
python run.py
```

Then open:

- Application — http://127.0.0.1:8000
- API documentation — http://127.0.0.1:8000/docs
- Health check — http://127.0.0.1:8000/health

### VS Code, step by step

1. Open the `ComicCraft` folder in VS Code.
2. Open a terminal (`Ctrl + \``).
3. `python -m venv .venv`
4. `.venv\Scripts\Activate.ps1`
5. `pip install -r requirements.txt`
6. `Copy-Item .env.example .env`
7. Paste your `GEMINI_API_KEY` (and `HF_API_KEY` if used) into `.env`.
8. `uvicorn app.main:app --reload`
9. Open http://127.0.0.1:8000
10. Open http://127.0.0.1:8000/docs

Select the `.venv` interpreter via **Ctrl + Shift + P → Python: Select Interpreter**.

---

## 5. Routes

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Landing page and comic creation workspace |
| POST | `/generate` | Form submission → renders the comic preview |
| POST | `/generate-comic/json` | JSON API → structured comic payload + PDF URL |
| GET | `/export-success` | Export confirmation page |
| POST | `/test-image` | Developer utility: single image from a raw prompt |
| GET | `/download` | Streams an exported PDF (path-traversal guarded) |
| GET | `/health` | Health and configuration probe |
| GET | `/docs` | Interactive Swagger UI |

### API example

```powershell
curl -X POST http://127.0.0.1:8000/generate-comic/json `
  -H "Content-Type: application/json" `
  -d '{\"story_prompt\":\"A brave fox discovers a mysterious portal inside an enchanted forest.\",\"character_name\":\"Finn\",\"setting\":\"Enchanted Forest\",\"tone\":\"Adventure\",\"art_style\":\"Comic Book\"}'
```

Response shape:

```json
{
  "success": true,
  "title": "Finn and the Whispering Portal",
  "character_name": "Finn",
  "setting": "Enchanted Forest",
  "tone": "Adventure",
  "art_style": "Comic Book",
  "panels": [
    {
      "panel_number": 1,
      "title": "The Forest's Edge",
      "scene_description": "...",
      "caption": "...",
      "narration": "...",
      "dialogue": ["FINN: Here we go."],
      "image_prompt": "...",
      "image_url": "/static/panels/..._panel_1.png"
    }
  ],
  "pdf_url": "/static/exports/..._20260923_120000_ab12cd.pdf",
  "warnings": []
}
```

---

## 6. Testing

```powershell
python -m pytest -q          # full suite
python -m pytest tests/test_services.py -v
```

The suite covers the homepage, health endpoint, OpenAPI schema, Pydantic validation,
error envelopes, path-traversal protection, AI-output normalisation, JSON recovery,
layout building, image generation and PDF export. Tests force
`IMAGE_PROVIDER=placeholder` so they never call paid services.

---

## 7. Troubleshooting

| Problem | Fix |
| --- | --- |
| `python` not recognised | Install Python 3.10+ from python.org and tick **Add Python to PATH**, then reopen the terminal. |
| `pip` not recognised / outdated | `python -m pip install --upgrade pip` |
| `.venv\Scripts\Activate.ps1 cannot be loaded` | `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`, then activate again. |
| "ComicCraft is not configured yet" | `GEMINI_API_KEY` is missing from `.env`; add it and restart the server. |
| "Your Gemini API key was rejected" | Regenerate the key in Google AI Studio and confirm the API is enabled for your project. |
| "The configured model is unavailable" | Change `GEMINI_OUTLINE_MODEL` / `GEMINI_STORY_MODEL` to a model your key can access. |
| "The AI returned an outline we could not read" | Transient malformed JSON — retry; the raw response is logged server-side. |
| "Stable Diffusion could not be loaded" | Install `torch`/`diffusers`, free up memory, or set `IMAGE_PROVIDER=huggingface_api`. |
| Hugging Face 401/404 | Check `HF_API_KEY`, accept the model licence on huggingface.co, verify `IMAGE_MODEL`. |
| CUDA out of memory | Lower `IMAGE_WIDTH`/`IMAGE_HEIGHT` to 384, reduce `IMAGE_STEPS`, or set `IMAGE_DEVICE=cpu`. |
| Image generation very slow | Expected on CPU. Use a GPU or the hosted provider. |
| PDF export failed | Confirm `fpdf2` is installed and `static/exports/` is writable. |
| `Address already in use` | `uvicorn app.main:app --reload --port 8001`, or on Windows: `netstat -ano \| findstr :8000` then `taskkill /PID <pid> /F`. |
| Static files 404 | Start Uvicorn from the project root so `static/` and `templates/` resolve. |

---

## 8. Design and accessibility notes

- Mobile-first CSS with breakpoints at 375 / 480 / 768 / 1024 / 1280 / 1440 px; no horizontal overflow at 320 px.
- Comic grid: 1 column on mobile, 2 columns from 768 px with the final odd panel centred full-width.
- Semantic HTML, labelled controls, `role="radiogroup"` selection groups with arrow-key navigation, visible focus rings, alt text and full `prefers-reduced-motion` support.
- Toasts replace `alert()`; inline field errors replace browser-default validation bubbles.

## 9. Extending

The service layer is intentionally modular: add a new class to `image_generator.py` and
register it in `_PROVIDERS` to swap illustration backends; swap text models through `.env`
alone. Persistence for user profiles, comic libraries and multi-page story arcs can be added
behind `comic_service.create_comic` without touching the routes or templates.
