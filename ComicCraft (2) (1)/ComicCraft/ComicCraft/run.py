"""Development entry point: python run.py"""

from __future__ import annotations

import uvicorn

from app.config import settings


def main() -> None:
    """Start the Uvicorn development server using configured host/port."""
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )


if __name__ == "__main__":
    main()
