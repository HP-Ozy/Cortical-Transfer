"""MemPack v0.1 Pydantic models. Normative reference: SPEC.md."""

from __future__ import annotations

import os
import time
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FORMAT_VERSION = "0.2.0"

# ponytail: inline ULID (Crockford base32, 10 ts chars + 16 random) beats a dependency.
_B32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_ulid() -> str:
    ts = int(time.time() * 1000)
    chars = [_B32[(ts >> (5 * i)) & 31] for i in range(9, -1, -1)]
    rand = int.from_bytes(os.urandom(10))
    chars += [_B32[(rand >> (5 * i)) & 31] for i in range(15, -1, -1)]
    return "".join(chars)


def now() -> datetime:
    return datetime.now(UTC)


Granularity = Literal["summary", "episode", "detail"]


class SemanticNode(BaseModel):
    # extra="ignore": SPEC §8 — importers MUST accept higher-minor packs by
    # ignoring unknown fields.
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=new_ulid)
    text: str
    granularity: Granularity = "episode"
    salience: float = Field(default=0.5, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=now)
    last_confirmed_at: datetime = Field(default_factory=now)
    superseded_by: str | None = None
    parent_id: str | None = None
    # real-world validity (ISO dates), distinct from created_at (ingestion time)
    valid_from: str | None = None
    valid_until: str | None = None
    source_refs: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class Manifest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    format_version: str = FORMAT_VERSION
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
    source_models: list[str] = Field(default_factory=list)
    generator: str = f"cortical-transfer/{FORMAT_VERSION}"
    content_hashes: dict[str, str] = Field(default_factory=dict)  # filename -> sha256 hex


class MemPack(BaseModel):
    """In-memory view of a MemPack directory."""

    model_config = ConfigDict(extra="forbid")

    manifest: Manifest = Field(default_factory=Manifest)
    identity: list[SemanticNode] = Field(default_factory=list)
    episodes: list[SemanticNode] = Field(default_factory=list)
    threads: list[SemanticNode] = Field(default_factory=list)
    style: str = ""

    def all_nodes(self) -> list[SemanticNode]:
        return self.identity + self.episodes + self.threads
