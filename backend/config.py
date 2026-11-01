import json
import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    token: str = ""
    origins: list[str] = field(default_factory=list)
    model_dir: Path = field(default_factory=lambda: ROOT / "models")

    @classmethod
    def load(cls):
        path = Path(os.environ.get("blank_config", ROOT / ".local" / "config.json"))
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(token=data["token"], origins=data["origins"])
