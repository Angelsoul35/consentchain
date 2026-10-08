"""Application configuration, loaded from environment variables (prefix ``CC_``)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CC_", env_file=".env", extra="ignore")

    environment: str = "local"

    # Classifier confidence below which a request is routed to a human reviewer
    # instead of being auto-decided.
    min_confidence: float = 0.55

    chain_enabled: bool = True
    chain_rpc_url: str = "http://anvil:8545"
    contract_address: str = ""
    chain_private_key: str = ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
