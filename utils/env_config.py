import os
from pathlib import Path
from typing import Dict

ENV_FILES = [Path(".env"), Path("env.local")]


def _apply_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def load_env_file(path: Path | str) -> None:
    _apply_env_file(Path(path))


def _load_env_files() -> None:
    for env_path in ENV_FILES:
        _apply_env_file(env_path)


_load_env_files()


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def get_openai_api_key() -> str:
    return _require_env("OPENAI_API_KEY")


def get_neo4j_credentials() -> Dict[str, str]:
    return {
        "uri": _require_env("NEO4J_URI"),
        "username": _require_env("NEO4J_USERNAME"),
        "password": _require_env("NEO4J_PASSWORD"),
    }
