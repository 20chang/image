from __future__ import annotations

from pydantic import BaseModel, Field


class FolderCreate(BaseModel):
    name: str = Field(min_length=1)


class FolderUpdate(BaseModel):
    name: str = Field(min_length=1)


class FolderOut(BaseModel):
    id: str
    name: str
    createdAt: str
    productCount: int = 0
    refCount: int = 0


class ProductCreate(BaseModel):
    folderId: str
    name: str = Field(min_length=1)
    market: str = ""
    facts: str = ""


class ProductUpdate(BaseModel):
    name: str | None = None
    market: str | None = None
    facts: str | None = None
    folderId: str | None = None


class ProductMove(BaseModel):
    folderId: str


class ProductOut(BaseModel):
    id: str
    folderId: str
    name: str
    market: str
    facts: str
    updatedAt: str
    refCount: int = 0
    coverUrl: str | None = None


class ReferenceMeta(BaseModel):
    source: str = ""
    purposes: list[str] = Field(default_factory=list)
    desc: str = ""


class ReferenceReorder(BaseModel):
    direction: str  # up | down


class ReferenceOut(BaseModel):
    id: str
    assetId: str
    productId: str
    url: str
    source: str
    purposes: list[str]
    desc: str
    status: str
    sortOrder: int = 0
