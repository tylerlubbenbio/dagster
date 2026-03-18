"""Load config from config.json; secrets are injected from env in code (not in config)."""

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = REPO_ROOT / "config.json"
ENV_PATH = REPO_ROOT / ".env"

# Which env var supplies each config path. Config file must not contain secrets.
_SECRETS = [
    # Target warehouse credentials
    (("target", "host"), "TARGET_HOST"),
    (("target", "database"), "TARGET_DATABASE"),
    (("target", "username"), "TARGET_USERNAME"),
    (("target", "password"), "TARGET_PASSWORD"),
    # Add source database credentials below (one per source)
    # (("databases", "source_name", "password"), "SOURCE_NAME_PASSWORD"),
    # Add API credentials below
    # (("example_api", "api_key"), "EXAMPLE_API_KEY"),
]


def _load_dotenv(path: Path):
    if not path.exists():
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                os.environ.setdefault(key, val)


def _set_path(cfg: dict, path: tuple, value: str):
    d = cfg
    for key in path[:-1]:
        d = d.setdefault(key, {})
    d[path[-1]] = value


def load_config():
    """Load config.json, overlay .env, inject secrets from env (mapping in this file)."""
    _load_dotenv(ENV_PATH)
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
    else:
        cfg = {}
    for path, env_var in _SECRETS:
        _set_path(cfg, path, os.environ.get(env_var, ""))
    return cfg
