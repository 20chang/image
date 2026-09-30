from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ProductRelation = Literal["same_product", "other_product", "no_product", "unknown"]
AiStatus = Literal["yes", "no", "unknown"]
PlanRole = Literal["primary", "detail", "usage", "composition", "style"]

PLAN_ROLES: set[str] = {"primary", "detail", "usage", "composition", "style"}
PRODUCT_RELATIONS: set[str] = {"same_product", "other_product", "no_product", "unknown"}
AI_STATUSES: set[str] = {"yes", "no", "unknown"}


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
    source: str | None = None
    purposes: list[str] | None = None
    desc: str | None = None
    productRelation: ProductRelation | None = None
    aiStatus: AiStatus | None = None


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
    productRelation: ProductRelation = "unknown"
    aiStatus: AiStatus = "unknown"


class ReferenceUsageItem(BaseModel):
    refImageId: str = Field(min_length=1)
    roles: list[str] = Field(default_factory=list)
    useFor: str = ""
    ignore: str = ""


class ImagePlanCreate(BaseModel):
    name: str = Field(min_length=1)
    imageUsage: str = "商品主图"
    refImageIds: list[str] = Field(default_factory=list)
    drawingRequest: str = ""
    prompt: str = ""
    basedOnPlanId: str | None = None
    referenceUsage: list[ReferenceUsageItem] | None = None


class ImagePlanUpdate(BaseModel):
    name: str | None = None
    imageUsage: str | None = None
    refImageIds: list[str] | None = None
    drawingRequest: str | None = None
    prompt: str | None = None
    referenceUsage: list[ReferenceUsageItem] | None = None


class ImagePlanOut(BaseModel):
    id: str
    productId: str
    name: str
    imageUsage: str
    refImageIds: list[str]
    drawingRequest: str
    prompt: str
    status: str
    basedOnPlanId: str | None = None
    createdAt: str
    updatedAt: str
    confirmedAt: str | None = None
    referenceUsage: list[ReferenceUsageItem] = Field(default_factory=list)
    usageSummary: str = ""
