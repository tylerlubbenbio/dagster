"""Load config from config.json; secrets are injected from env in code (not in config)."""

import json
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = REPO_ROOT / "config.json"
ENV_PATH = REPO_ROOT / ".env"

# Which env var supplies each config path. Config file must not contain secrets.
_SECRETS = [
    # Snowflake target warehouse
    (("target", "account"), "SNOWFLAKE_ACCOUNT"),
    (("target", "database"), "TARGET_DATABASE"),
    (("target", "username"), "TARGET_USERNAME"),
    (("target", "password"), "TARGET_PASSWORD"),
    (("target", "role"), "SNOWFLAKE_ROLE"),
    (("target", "warehouse"), "SNOWFLAKE_WAREHOUSE"),
    # MySQL Dock source
    (("sources", "mysql_dock", "host"), "MYSQL_DOCK_HOST"),
    (("sources", "mysql_dock", "username"), "MYSQL_DOCK_USERNAME"),
    (("sources", "mysql_dock", "password"), "MYSQL_DOCK_PASSWORD"),
    # MongoDB Goldlantern source
    (("sources", "mongo_goldlantern", "uri"), "MONGO_GOLDLANTERN_URI"),
    # API sources
    (("sources", "klaviyo", "api_key"), "KLAVIYO_API_KEY"),
    (("sources", "meta", "access_token"), "META_ACCESS_TOKEN"),
    (("sources", "meta", "ad_account_id"), "META_AD_ACCOUNT_ID"),
    (("sources", "google_ads_gallant_seto", "developer_token"), "GOOGLE_ADS_DEVELOPER_TOKEN"),
    (("sources", "google_ads_gallant_seto", "customer_id"), "GOOGLE_ADS_GALLANT_SETO_CUSTOMER_ID"),
    (("sources", "google_ads_gallant_seto", "refresh_token"), "GOOGLE_ADS_GALLANT_SETO_REFRESH_TOKEN"),
    (("sources", "google_ads_gallant_seto", "client_id"), "GOOGLE_ADS_GALLANT_SETO_CLIENT_ID"),
    (("sources", "google_ads_gallant_seto", "client_secret"), "GOOGLE_ADS_GALLANT_SETO_CLIENT_SECRET"),
    (("sources", "google_ads_noot", "developer_token"), "GOOGLE_ADS_DEVELOPER_TOKEN"),
    (("sources", "google_ads_noot", "customer_id"), "GOOGLE_ADS_NOOT_CUSTOMER_ID"),
    (("sources", "google_ads_noot", "refresh_token"), "GOOGLE_ADS_NOOT_REFRESH_TOKEN"),
    (("sources", "google_ads_noot", "client_id"), "GOOGLE_ADS_NOOT_CLIENT_ID"),
    (("sources", "google_ads_noot", "client_secret"), "GOOGLE_ADS_NOOT_CLIENT_SECRET"),
    (("sources", "ga4", "credentials_json"), "GA4_CREDENTIALS_JSON"),
    (("sources", "gtm", "credentials_json"), "GTM_CREDENTIALS_JSON"),
    (("sources", "amazon_ads", "client_id"), "AMAZON_ADS_CLIENT_ID"),
    (("sources", "amazon_ads", "client_secret"), "AMAZON_ADS_CLIENT_SECRET"),
    (("sources", "amazon_ads", "refresh_token"), "AMAZON_ADS_REFRESH_TOKEN"),
    (("sources", "amazon_ads", "profile_id"), "AMAZON_ADS_PROFILE_ID"),
    (("sources", "amazon_selling_partner", "client_id"), "AMAZON_SP_CLIENT_ID"),
    (("sources", "amazon_selling_partner", "client_secret"), "AMAZON_SP_CLIENT_SECRET"),
    (("sources", "amazon_selling_partner", "refresh_token"), "AMAZON_SP_REFRESH_TOKEN"),
    (("sources", "tiktok_ads", "access_token"), "TIKTOK_ADS_ACCESS_TOKEN"),
    (("sources", "tiktok_ads", "advertiser_id"), "TIKTOK_ADS_ADVERTISER_ID"),
    (("sources", "pacvuedsp", "api_key"), "PACVUEDSP_API_KEY"),
    (("sources", "refersion", "api_key"), "REFERSION_API_KEY"),
    (("sources", "refersion", "api_secret"), "REFERSION_API_SECRET"),
    (("sources", "triple_whale", "api_key"), "TRIPLE_WHALE_API_KEY"),
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
