"""The base of every config model: unknown keys are refused and values never change."""

from pydantic import BaseModel, ConfigDict


class ConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
