from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


Platform = Literal["youtube", "instagram", "xiaohongshu", "threads", "douyin"]
AssetKind = Literal["video", "thumbnail", "image"]


class AnalyzeRequest(BaseModel):
    url: str = Field(min_length=8, max_length=4096)


class DownloadRequest(BaseModel):
    url: str = Field(min_length=8, max_length=4096)
    asset_id: str = Field(min_length=3, max_length=256)


class MediaAsset(BaseModel):
    id: str
    kind: AssetKind
    label: str
    width: int | None = None
    height: int | None = None
    ext: str | None = None
    filesize: int | None = None
    preview_url: str | None = None


class AnalyzeResponse(BaseModel):
    platform: Platform
    title: str | None = None
    author: str | None = None
    webpage_url: str
    preview_url: str | None = None
    assets: list[MediaAsset]


class HealthResponse(BaseModel):
    ok: bool = True
    service: str = "insta-thread-api"
