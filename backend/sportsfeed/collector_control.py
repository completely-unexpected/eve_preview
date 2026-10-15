from pathlib import Path
import os
from django.conf import settings


def pause_file():
    return Path(os.environ.get("ODDSPORTAL_RUNTIME_DIR", settings.BASE_DIR / ".local-oddsportal-runtime")) / "paused"


def is_paused():
    return pause_file().exists()


def set_paused(paused):
    path = pause_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    if paused:
        path.touch()
    else:
        path.unlink(missing_ok=True)
