"""Main entry point for the application."""

import uvicorn

from eqtr.api import app
from eqtr.log import get_logger
from eqtr.settings import SETTINGS

logger = get_logger(__name__)


def main() -> None:
    """Entry point for the application."""
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level=SETTINGS.log_level)  # noqa: S104


if __name__ == "__main__":
    main()
