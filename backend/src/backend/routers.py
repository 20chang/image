from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi import Path as PathParam

from .db import UPLOAD_DIR, connect, now_iso
from .planner import PlannerError, load_config, parse_plan_output, run_planner
from .schemas import (
    PLAN_ROLES,
    AdoptRunRequest,
    FolderCreate,
    FolderOut,
    FolderUpdate,
    ImagePlanCreate,
    ImagePlanOut,
    ImagePlanUpdate,
    PlanRunOut,
    ProductCreate,
    ProductMove,
    ProductOut,
    ProductUpdate,
    ReferenceMeta,
    ReferenceOut,
    ReferenceReorder,
    ReferenceUsageItem,
)
from .skill_preview.assemble import assemble_from_case
from .skill_preview.loader import load_plan_case

router = APIRouter(prefix="/api")

IMG_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def _new_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def _folder_row_to_out(row, product_count: int, ref_count: int) -> FolderOut:
    return FolderOut(
        id=row["id"],
        name=row["name"],
        createdAt=row["created_at"],
        productCount=product_count,
        refCount=ref_count,
    )


def _product_row_to_out(row, ref_count: int, cover_url: str | None) -> ProductOut:
    return ProductOut(
        id=row["id"],
        folderId=row["folder_id"],
        name=row["name"],
        market=row["market"],
        facts=row["facts"],
        updatedAt=row["updated_at"],
        refCount=ref_count,
        coverUrl=cover_url,
    )


def _ref_row_to_out(row) -> ReferenceOut:
    return ReferenceOut(
        id=row["id"],
        assetId=row["asset_id"],
        productId=row["product_id"],
        url=row["url"],
        source=row["source"],
        purposes=json.loads(row["purposes"] or "[]"),
        desc=row["desc"],
        status=row["status"],
        sortOrder=row["sort_order"],
        productRelation=row["product_relation"],
        aiStatus=row["ai_status"],
    )


def _build_usage_summary(usage: list[dict]) -> str:
    if not usage:
        return ""
    parts: list[str] = []
    for idx, item in enumerate(usage):
        label = chr(ord("A") + idx)
        roles = item.get("roles") or []
        use_for = (item.get("useFor") or "").strip()
        ignore = (item.get("ignore") or "").strip()
        if "primary" in roles:
            phrase = f"{label}图提供{use_for or '主体外观'}"
        elif "detail" in roles:
            phrase = f"{label}图补充{use_for or '细节'}"
        elif "composition" in roles:
            phrase = f"{label}图只参考构图"
        elif "style" in roles:
            phrase = f"{label}图参考视觉风格"
        elif "usage" in roles:
            phrase = f"{label}图参考安装与使用"
        elif use_for:
            phrase = f"{label}图{use_for}"
        else:
            phrase = f"{label}图作参考"
        if ignore:
            phrase = f"{phrase}，忽略{ignore}"
        parts.append(phrase)
    return "；".join(parts) + "。"


def _usage_items(raw: str) -> list[dict]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return data


def _plan_row_to_out(row) -> ImagePlanOut:
    usage = _usage_items(row["reference_usage"])
    items = [ReferenceUsageItem(**u) for u in usage]
    return ImagePlanOut(
        id=row["id"],
        productId=row["product_id"],
        name=row["name"],
        imageUsage=row["image_usage"],
        refImageIds=json.loads(row["ref_image_ids"] or "[]"),
        drawingRequest=row["drawing_request"],
        prompt=row["prompt"],
        status=row["status"],
        basedOnPlanId=row["based_on_plan_id"],
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
        confirmedAt=row["confirmed_at"],
        referenceUsage=items,
        usageSummary=_build_usage_summary(usage),
        family=row["family"] or "main",
        designNotes=row["design_notes"] or "",
        openQuestions=_json_str_list(row["open_questions"]),
    )


def _json_str_list(raw: str | None) -> list[str]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(x) for x in data]


def _require_plan_ref_ids(conn, product_id: str, ref_image_ids: list[str]) -> None:
    seen: set[str] = set()
    for rid in ref_image_ids:
        if rid in seen:
            raise HTTPException(422, f"duplicate refImageId: {rid}")
        seen.add(rid)
        row = conn.execute(
            "SELECT product_id FROM ref_images WHERE id = ?", (rid,)
        ).fetchone()
        if not row or row["product_id"] != product_id:
            raise HTTPException(422, f"reference image not in product: {rid}")


def _normalize_usage(
    conn, product_id: str, usage: list[ReferenceUsageItem] | list[dict]
) -> list[dict]:
    items: list[dict] = []
    seen: set[str] = set()
    primary_count = 0
    for entry in usage:
        if isinstance(entry, ReferenceUsageItem):
            ref_id = entry.refImageId
            roles = list(entry.roles)
            use_for = entry.useFor
            ignore = entry.ignore
        else:
            ref_id = entry.get("refImageId") or ""
            roles = list(entry.get("roles") or [])
            use_for = entry.get("useFor") or ""
            ignore = entry.get("ignore") or ""
        if not ref_id:
            raise HTTPException(422, "referenceUsage.refImageId required")
        if ref_id in seen:
            raise HTTPException(
                422, f"duplicate refImageId in referenceUsage: {ref_id}"
            )
        seen.add(ref_id)
        row = conn.execute(
            "SELECT product_id FROM ref_images WHERE id = ?", (ref_id,)
        ).fetchone()
        if not row or row["product_id"] != product_id:
            raise HTTPException(422, f"reference image not in product: {ref_id}")
        for role in roles:
            if role not in PLAN_ROLES:
                raise HTTPException(422, f"unknown role: {role}")
        if "primary" in roles:
            primary_count += 1
            if primary_count > 1:
                raise HTTPException(422, "at most one primary reference")
        items.append(
            {
                "refImageId": ref_id,
                "roles": roles,
                "useFor": use_for,
                "ignore": ignore,
            }
        )
    return items


def _usage_to_ids(usage: list[dict]) -> list[str]:
    return [u["refImageId"] for u in usage]


ALLOWED_PLAN_FAMILIES = {"main"}


def _require_supported_family(family: str) -> str:
    value = (family or "").strip()
    if value not in ALLOWED_PLAN_FAMILIES:
        raise HTTPException(
            422,
            f"unsupported family: {value!r}; only {sorted(ALLOWED_PLAN_FAMILIES)} this round",
        )
    return value


def _skeleton_usage(ref_image_ids: list[str]) -> list[dict]:
    return [
        {"refImageId": rid, "roles": [], "useFor": "", "ignore": ""}
        for rid in ref_image_ids
    ]


def _product_stats(conn, product_id: str) -> tuple[int, str | None]:
    rows = conn.execute(
        "SELECT url, status FROM ref_images WHERE product_id = ? ORDER BY sort_order",
        (product_id,),
    ).fetchall()
    ok = [r for r in rows if r["status"] == "success"]
    cover = ok[0]["url"] if ok else None
    return len(ok), cover


def _folder_counts(conn, folder_id: str) -> tuple[int, int]:
    pcount = conn.execute(
        "SELECT COUNT(*) AS c FROM products WHERE folder_id = ?",
        (folder_id,),
    ).fetchone()["c"]
    rcount = conn.execute(
        """
        SELECT COUNT(*) AS c FROM ref_images r
        JOIN products p ON p.id = r.product_id
        WHERE p.folder_id = ? AND r.status = 'success'
        """,
        (folder_id,),
    ).fetchone()["c"]
    return pcount, rcount


# --- Folders ---


@router.get("/folders", response_model=list[FolderOut])
def list_folders() -> list[FolderOut]:
    with connect() as conn:
        folders = conn.execute(
            "SELECT * FROM folders ORDER BY created_at DESC, id"
        ).fetchall()
        out: list[FolderOut] = []
        for f in folders:
            pcount, rcount = _folder_counts(conn, f["id"])
            out.append(_folder_row_to_out(f, pcount, rcount))
        return out


@router.get("/folders/{folder_id}", response_model=FolderOut)
def get_folder(folder_id: str = PathParam()) -> FolderOut:
    with connect() as conn:
        f = conn.execute("SELECT * FROM folders WHERE id = ?", (folder_id,)).fetchone()
        if not f:
            raise HTTPException(404, "folder not found")
        pcount, rcount = _folder_counts(conn, folder_id)
        return _folder_row_to_out(f, pcount, rcount)


@router.post("/folders", response_model=FolderOut, status_code=201)
def create_folder(body: FolderCreate) -> FolderOut:
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "folder name required")
    with connect() as conn:
        dup = conn.execute("SELECT id FROM folders WHERE name = ?", (name,)).fetchone()
        if dup:
            raise HTTPException(409, "folder name already exists")
        fid = _new_id("f")
        conn.execute(
            "INSERT INTO folders (id, name, created_at) VALUES (?, ?, ?)",
            (fid, name, now_iso()),
        )
        row = conn.execute("SELECT * FROM folders WHERE id = ?", (fid,)).fetchone()
        return _folder_row_to_out(row, 0, 0)


@router.patch("/folders/{folder_id}", response_model=FolderOut)
def rename_folder(body: FolderUpdate, folder_id: str = PathParam()) -> FolderOut:
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "folder name required")
    with connect() as conn:
        f = conn.execute("SELECT * FROM folders WHERE id = ?", (folder_id,)).fetchone()
        if not f:
            raise HTTPException(404, "folder not found")
        dup = conn.execute(
            "SELECT id FROM folders WHERE name = ? AND id != ?",
            (name, folder_id),
        ).fetchone()
        if dup:
            raise HTTPException(409, "folder name already exists")
        conn.execute("UPDATE folders SET name = ? WHERE id = ?", (name, folder_id))
        row = conn.execute(
            "SELECT * FROM folders WHERE id = ?", (folder_id,)
        ).fetchone()
        pcount, rcount = _folder_counts(conn, folder_id)
        return _folder_row_to_out(row, pcount, rcount)


@router.delete("/folders/{folder_id}", status_code=204)
def delete_folder(folder_id: str = PathParam()) -> None:
    with connect() as conn:
        f = conn.execute("SELECT id FROM folders WHERE id = ?", (folder_id,)).fetchone()
        if not f:
            raise HTTPException(404, "folder not found")
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM products WHERE folder_id = ?",
            (folder_id,),
        ).fetchone()["c"]
        if count > 0:
            raise HTTPException(
                409,
                f"folder still has {count} product(s); move or delete them first",
            )
        conn.execute("DELETE FROM folders WHERE id = ?", (folder_id,))


# --- Products ---


@router.get("/products", response_model=list[ProductOut])
def list_products(
    folderId: str | None = None, name: str | None = None
) -> list[ProductOut]:
    sql = "SELECT * FROM products WHERE 1=1"
    params: list[str] = []
    if folderId:
        sql += " AND folder_id = ?"
        params.append(folderId)
    if name and name.strip():
        sql += " AND LOWER(name) LIKE ?"
        params.append(f"%{name.strip().lower()}%")
    sql += " ORDER BY updated_at DESC, id"
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
        out: list[ProductOut] = []
        for r in rows:
            ref_count, cover = _product_stats(conn, r["id"])
            out.append(_product_row_to_out(r, ref_count, cover))
        return out


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: str = PathParam()) -> ProductOut:
    with connect() as conn:
        r = conn.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if not r:
            raise HTTPException(404, "product not found")
        ref_count, cover = _product_stats(conn, product_id)
        return _product_row_to_out(r, ref_count, cover)


@router.post("/products", response_model=ProductOut, status_code=201)
def create_product(body: ProductCreate) -> ProductOut:
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "product name required")
    with connect() as conn:
        folder = conn.execute(
            "SELECT id FROM folders WHERE id = ?", (body.folderId,)
        ).fetchone()
        if not folder:
            raise HTTPException(404, "folder not found")
        pid = _new_id("p")
        conn.execute(
            """
            INSERT INTO products (id, folder_id, name, market, facts, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                pid,
                body.folderId,
                name,
                body.market.strip(),
                body.facts.strip(),
                now_iso(),
            ),
        )
        r = conn.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
        return _product_row_to_out(r, 0, None)


@router.patch("/products/{product_id}", response_model=ProductOut)
def update_product(body: ProductUpdate, product_id: str = PathParam()) -> ProductOut:
    with connect() as conn:
        r = conn.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if not r:
            raise HTTPException(404, "product not found")
        name = r["name"] if body.name is None else body.name.strip()
        if not name:
            raise HTTPException(422, "product name required")
        market = r["market"] if body.market is None else body.market.strip()
        facts = r["facts"] if body.facts is None else body.facts.strip()
        folder_id = r["folder_id"] if body.folderId is None else body.folderId
        if body.folderId is not None:
            folder = conn.execute(
                "SELECT id FROM folders WHERE id = ?", (folder_id,)
            ).fetchone()
            if not folder:
                raise HTTPException(404, "folder not found")
        conn.execute(
            """
            UPDATE products
            SET name = ?, market = ?, facts = ?, folder_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (name, market, facts, folder_id, now_iso(), product_id),
        )
        r = conn.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        ref_count, cover = _product_stats(conn, product_id)
        return _product_row_to_out(r, ref_count, cover)


@router.post("/products/{product_id}/move", response_model=ProductOut)
def move_product(body: ProductMove, product_id: str = PathParam()) -> ProductOut:
    with connect() as conn:
        r = conn.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if not r:
            raise HTTPException(404, "product not found")
        folder = conn.execute(
            "SELECT id FROM folders WHERE id = ?", (body.folderId,)
        ).fetchone()
        if not folder:
            raise HTTPException(404, "target folder not found")
        conn.execute(
            "UPDATE products SET folder_id = ?, updated_at = ? WHERE id = ?",
            (body.folderId, now_iso(), product_id),
        )
        r = conn.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        ref_count, cover = _product_stats(conn, product_id)
        return _product_row_to_out(r, ref_count, cover)


@router.delete("/products/{product_id}", status_code=204)
def delete_product(product_id: str = PathParam()) -> None:
    with connect() as conn:
        r = conn.execute(
            "SELECT id FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if not r:
            raise HTTPException(404, "product not found")
        conn.execute("DELETE FROM ref_images WHERE product_id = ?", (product_id,))
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))


# --- Reference images ---


@router.get("/products/{product_id}/references", response_model=list[ReferenceOut])
def list_references(product_id: str = PathParam()) -> list[ReferenceOut]:
    with connect() as conn:
        r = conn.execute(
            "SELECT id FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if not r:
            raise HTTPException(404, "product not found")
        rows = conn.execute(
            "SELECT * FROM ref_images WHERE product_id = ? ORDER BY sort_order, id",
            (product_id,),
        ).fetchall()
        return [_ref_row_to_out(x) for x in rows]


@router.post(
    "/products/{product_id}/references",
    response_model=ReferenceOut,
    status_code=201,
)
async def upload_reference(
    product_id: str = PathParam(),
    file: UploadFile = File(...),  # noqa: B008
) -> ReferenceOut:
    with connect() as conn:
        r = conn.execute(
            "SELECT id FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if not r:
            raise HTTPException(404, "product not found")

    suffix = Path(file.filename or "image.png").suffix or ".png"
    if suffix.lower() not in IMG_SUFFIXES:
        raise HTTPException(422, "only image files are allowed")
    rid = _new_id("r")
    filename = f"{rid}{suffix}"
    dest = UPLOAD_DIR / filename
    content = await file.read()
    if not content:
        raise HTTPException(422, "empty file")
    dest.write_bytes(content)

    url = f"/uploads/{filename}"
    with connect() as conn:
        max_order = conn.execute(
            """
            SELECT COALESCE(MAX(sort_order), -1) AS m FROM ref_images
            WHERE product_id = ?
            """,
            (product_id,),
        ).fetchone()["m"]
        conn.execute(
            """
            INSERT INTO ref_images
              (id, asset_id, product_id, url, source, purposes, desc, status, sort_order,
               product_relation, ai_status, attrs_migrated)
            VALUES (?, ?, ?, ?, '', '[]', '', 'success', ?, 'unknown', 'unknown', 1)
            """,
            (rid, f"asset_{rid}", product_id, url, max_order + 1),
        )
        row = conn.execute("SELECT * FROM ref_images WHERE id = ?", (rid,)).fetchone()
        return _ref_row_to_out(row)


@router.patch("/references/{ref_id}", response_model=ReferenceOut)
def update_reference_meta(
    body: ReferenceMeta, ref_id: str = PathParam()
) -> ReferenceOut:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM ref_images WHERE id = ?", (ref_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "reference not found")
        if body.desc == "error":
            raise HTTPException(500, "simulated save failure")
        source = row["source"] if body.source is None else body.source
        if body.purposes is None:
            purposes = row["purposes"]
        else:
            purposes = json.dumps(body.purposes, ensure_ascii=False)
        desc = row["desc"] if body.desc is None else body.desc
        product_relation = (
            row["product_relation"]
            if body.productRelation is None
            else body.productRelation
        )
        ai_status = row["ai_status"] if body.aiStatus is None else body.aiStatus
        # Explicit new-field saves must not be overwritten by later migration backfill.
        attrs_migrated = (
            1
            if (body.productRelation is not None or body.aiStatus is not None)
            else row["attrs_migrated"]
        )
        conn.execute(
            """
            UPDATE ref_images
            SET source = ?, purposes = ?, desc = ?,
                product_relation = ?, ai_status = ?, attrs_migrated = ?
            WHERE id = ?
            """,
            (
                source,
                purposes,
                desc,
                product_relation,
                ai_status,
                attrs_migrated,
                ref_id,
            ),
        )
        row = conn.execute(
            "SELECT * FROM ref_images WHERE id = ?", (ref_id,)
        ).fetchone()
        return _ref_row_to_out(row)


@router.post("/references/{ref_id}/reorder", response_model=list[ReferenceOut])
def reorder_reference(
    body: ReferenceReorder, ref_id: str = PathParam()
) -> list[ReferenceOut]:
    if body.direction not in ("up", "down"):
        raise HTTPException(422, "direction must be up or down")
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM ref_images WHERE id = ?", (ref_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "reference not found")
        product_id = row["product_id"]
        rows = conn.execute(
            "SELECT * FROM ref_images WHERE product_id = ? ORDER BY sort_order, id",
            (product_id,),
        ).fetchall()
        items = list(rows)
        idx = next(i for i, r in enumerate(items) if r["id"] == ref_id)
        swap = idx - 1 if body.direction == "up" else idx + 1
        if 0 <= swap < len(items):
            a, b = items[idx], items[swap]
            conn.execute(
                "UPDATE ref_images SET sort_order = ? WHERE id = ?",
                (b["sort_order"], a["id"]),
            )
            conn.execute(
                "UPDATE ref_images SET sort_order = ? WHERE id = ?",
                (a["sort_order"], b["id"]),
            )
        rows = conn.execute(
            "SELECT * FROM ref_images WHERE product_id = ? ORDER BY sort_order, id",
            (product_id,),
        ).fetchall()
        return [_ref_row_to_out(x) for x in rows]


@router.delete("/references/{ref_id}", status_code=204)
def delete_reference(ref_id: str = PathParam()) -> None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM ref_images WHERE id = ?", (ref_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "reference not found")
        referencing = conn.execute(
            """
            SELECT id, name, ref_image_ids, reference_usage FROM image_plans
            """
        ).fetchall()
        blocked: list[str] = []
        for plan in referencing:
            ids = set(json.loads(plan["ref_image_ids"] or "[]"))
            for item in _usage_items(plan["reference_usage"]):
                if item.get("refImageId"):
                    ids.add(item["refImageId"])
            if ref_id in ids:
                blocked.append(plan["name"] or plan["id"])
        if blocked:
            raise HTTPException(
                409,
                "reference is used by plans: " + ", ".join(blocked),
            )
        conn.execute("DELETE FROM ref_images WHERE id = ?", (ref_id,))


# --- Image plans ---


@router.get("/products/{product_id}/plans", response_model=list[ImagePlanOut])
def list_image_plans(product_id: str = PathParam()) -> list[ImagePlanOut]:
    with connect() as conn:
        product = conn.execute(
            "SELECT id FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if not product:
            raise HTTPException(404, "product not found")
        rows = conn.execute(
            """
            SELECT * FROM image_plans WHERE product_id = ?
            ORDER BY created_at, id
            """,
            (product_id,),
        ).fetchall()
        return [_plan_row_to_out(r) for r in rows]


@router.get("/plans/{plan_id}", response_model=ImagePlanOut)
def get_image_plan(plan_id: str = PathParam()) -> ImagePlanOut:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM image_plans WHERE id = ?", (plan_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "plan not found")
        return _plan_row_to_out(row)


@router.post(
    "/products/{product_id}/plans",
    response_model=ImagePlanOut,
    status_code=201,
)
def create_image_plan(
    body: ImagePlanCreate, product_id: str = PathParam()
) -> ImagePlanOut:
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "plan name required")
    family = _require_supported_family(body.family)
    with connect() as conn:
        product = conn.execute(
            "SELECT id FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if not product:
            raise HTTPException(404, "product not found")
        if body.referenceUsage is not None:
            usage = _normalize_usage(conn, product_id, body.referenceUsage)
            ref_image_ids = _usage_to_ids(usage)
            if body.refImageIds and body.refImageIds != ref_image_ids:
                _require_plan_ref_ids(conn, product_id, body.refImageIds)
                if set(body.refImageIds) != set(ref_image_ids):
                    raise HTTPException(
                        422,
                        "refImageIds and referenceUsage must reference the same images",
                    )
        else:
            _require_plan_ref_ids(conn, product_id, body.refImageIds)
            usage = _skeleton_usage(body.refImageIds)
            ref_image_ids = body.refImageIds
        if body.basedOnPlanId is not None:
            src = conn.execute(
                "SELECT product_id FROM image_plans WHERE id = ?",
                (body.basedOnPlanId,),
            ).fetchone()
            if not src or src["product_id"] != product_id:
                raise HTTPException(422, "basedOnPlanId must be a plan of this product")
        plan_id = _new_id("pl")
        ts = now_iso()
        conn.execute(
            """
            INSERT INTO image_plans (
                id, product_id, name, image_usage, ref_image_ids,
                drawing_request, prompt, status, based_on_plan_id,
                created_at, updated_at, confirmed_at, reference_usage,
                family, design_notes, open_questions
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, NULL, ?, ?, ?, ?)
            """,
            (
                plan_id,
                product_id,
                name,
                body.imageUsage,
                json.dumps(ref_image_ids, ensure_ascii=False),
                body.drawingRequest,
                body.prompt,
                body.basedOnPlanId,
                ts,
                ts,
                json.dumps(usage, ensure_ascii=False),
                family,
                body.designNotes,
                json.dumps(body.openQuestions, ensure_ascii=False),
            ),
        )
        row = conn.execute(
            "SELECT * FROM image_plans WHERE id = ?", (plan_id,)
        ).fetchone()
        return _plan_row_to_out(row)


@router.patch("/plans/{plan_id}", response_model=ImagePlanOut)
def update_image_plan(
    body: ImagePlanUpdate, plan_id: str = PathParam()
) -> ImagePlanOut:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM image_plans WHERE id = ?", (plan_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "plan not found")
        if row["status"] != "draft":
            raise HTTPException(409, "confirmed plan is immutable")
        name = row["name"] if body.name is None else body.name.strip()
        if not name:
            raise HTTPException(422, "plan name required")
        image_usage = row["image_usage"] if body.imageUsage is None else body.imageUsage
        family = (
            (row["family"] or "main")
            if body.family is None
            else _require_supported_family(body.family)
        )
        if body.referenceUsage is not None:
            usage = _normalize_usage(conn, row["product_id"], body.referenceUsage)
            ref_image_ids = _usage_to_ids(usage)
        elif body.refImageIds is not None:
            _require_plan_ref_ids(conn, row["product_id"], body.refImageIds)
            ref_image_ids = body.refImageIds
            usage = _skeleton_usage(ref_image_ids)
        else:
            ref_image_ids = json.loads(row["ref_image_ids"] or "[]")
            usage = _usage_items(row["reference_usage"])
        drawing_request = (
            row["drawing_request"]
            if body.drawingRequest is None
            else body.drawingRequest
        )
        prompt = row["prompt"] if body.prompt is None else body.prompt
        conn.execute(
            """
            UPDATE image_plans
            SET name = ?, image_usage = ?, ref_image_ids = ?,
                drawing_request = ?, prompt = ?, updated_at = ?,
                reference_usage = ?, family = ?
            WHERE id = ?
            """,
            (
                name,
                image_usage,
                json.dumps(ref_image_ids, ensure_ascii=False),
                drawing_request,
                prompt,
                now_iso(),
                json.dumps(usage, ensure_ascii=False),
                family,
                plan_id,
            ),
        )
        row = conn.execute(
            "SELECT * FROM image_plans WHERE id = ?", (plan_id,)
        ).fetchone()
        return _plan_row_to_out(row)


@router.post("/plans/{plan_id}/confirm", response_model=ImagePlanOut)
def confirm_image_plan(plan_id: str = PathParam()) -> ImagePlanOut:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM image_plans WHERE id = ?", (plan_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "plan not found")
        if row["status"] != "draft":
            raise HTTPException(409, "plan already confirmed")
        usage = _usage_items(row["reference_usage"])
        incomplete = [u.get("refImageId", "") for u in usage if not u.get("roles")]
        if incomplete:
            raise HTTPException(
                422,
                "selected images need roles before confirm: " + ", ".join(incomplete),
            )
        ts = now_iso()
        conn.execute(
            """
            UPDATE image_plans
            SET status = 'confirmed', confirmed_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (ts, ts, plan_id),
        )
        row = conn.execute(
            "SELECT * FROM image_plans WHERE id = ?", (plan_id,)
        ).fetchone()
        return _plan_row_to_out(row)


# ---------- 规划运行记录 / skill-run / adopt ----------


def _rules_snapshot(loaded_paths: list[str]) -> list[dict[str, str]]:
    snapshot: list[dict[str, str]] = []
    for p in loaded_paths:
        path = Path(p)
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
        snapshot.append({"path": str(path), "sha256": digest})
    return snapshot


def _run_row_to_out(row) -> PlanRunOut:
    return PlanRunOut(
        id=row["id"],
        planId=row["plan_id"],
        status=row["status"],
        plannerModel=row["planner_model"] or "",
        systemPrompt=row["system_prompt"] or "",
        userPrompt=row["user_prompt"] or "",
        inputRefIds=_json_str_list(row["input_ref_ids"]),
        rulesSnapshot=_usage_items(row["rules_snapshot"]),
        rawOutput=row["raw_output"],
        designNotes=row["design_notes"],
        openQuestions=_json_str_list(row["open_questions"] or "[]"),
        generatedPrompt=row["generated_prompt"],
        refUsageNotes=row["ref_usage_notes"],
        error=row["error"],
        createdAt=row["created_at"],
        adoptedAt=row["adopted_at"],
    )


def _insert_plan_run(
    conn,
    *,
    plan_id: str,
    status: str,
    planner_model: str,
    system_prompt: str = "",
    user_prompt: str = "",
    input_ref_ids: list[str] | None = None,
    rules_snapshot: list[dict] | None = None,
    raw_output: str | None = None,
    design_notes: str | None = None,
    open_questions: list[str] | None = None,
    generated_prompt: str | None = None,
    ref_usage_notes: str | None = None,
    error: str | None = None,
) -> str:
    run_id = _new_id("run")
    conn.execute(
        """
        INSERT INTO plan_runs (
            id, plan_id, status, planner_model, system_prompt, user_prompt,
            input_ref_ids, rules_snapshot, raw_output, design_notes,
            open_questions, generated_prompt, ref_usage_notes, error,
            created_at, adopted_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
        """,
        (
            run_id,
            plan_id,
            status,
            planner_model,
            system_prompt,
            user_prompt,
            json.dumps(input_ref_ids or [], ensure_ascii=False),
            json.dumps(rules_snapshot or [], ensure_ascii=False),
            raw_output,
            design_notes,
            json.dumps(open_questions or [], ensure_ascii=False),
            generated_prompt,
            ref_usage_notes,
            error,
            now_iso(),
        ),
    )
    return run_id


def _get_run(conn, run_id: str):
    return conn.execute("SELECT * FROM plan_runs WHERE id = ?", (run_id,)).fetchone()


@router.get("/plans/{plan_id}/runs", response_model=list[PlanRunOut])
def list_plan_runs(plan_id: str = PathParam()) -> list[PlanRunOut]:
    with connect() as conn:
        plan = conn.execute(
            "SELECT id FROM image_plans WHERE id = ?", (plan_id,)
        ).fetchone()
        if not plan:
            raise HTTPException(404, "plan not found")
        rows = conn.execute(
            "SELECT * FROM plan_runs WHERE plan_id = ? ORDER BY created_at DESC, id DESC",
            (plan_id,),
        ).fetchall()
        return [_run_row_to_out(r) for r in rows]


@router.post("/plans/{plan_id}/skill-run", response_model=PlanRunOut)
def skill_run(plan_id: str = PathParam()) -> PlanRunOut:
    with connect() as conn:
        plan = conn.execute(
            "SELECT * FROM image_plans WHERE id = ?", (plan_id,)
        ).fetchone()
        if not plan:
            raise HTTPException(404, "plan not found")
        if plan["status"] != "draft":
            raise HTTPException(409, "only draft plans can run skill")

        usage = _usage_items(plan["reference_usage"])
        has_primary = any("primary" in (u.get("roles") or []) for u in usage)
        if (plan["family"] or "main") == "main" and not has_primary:
            missing = [u.get("refImageId", "") for u in usage if not u.get("roles")]
            run_id = _insert_plan_run(
                conn,
                plan_id=plan_id,
                status="failed",
                planner_model="",
                error="missing_primary: main 族需要 primary 参考图"
                + (f"；未标角色: {', '.join(missing)}" if missing else ""),
            )
            row = _get_run(conn, run_id)
            return _run_row_to_out(row)

        try:
            case = load_plan_case(conn, plan_id)
            assembled = assemble_from_case(plan["family"] or "main", case)
        except Exception as exc:  # noqa: BLE001 - 落失败 run 再返回可读错误
            run_id = _insert_plan_run(
                conn,
                plan_id=plan_id,
                status="failed",
                planner_model="",
                error=f"assemble_failed: {exc}",
            )
            row = _get_run(conn, run_id)
            return _run_row_to_out(row)

        messages = assembled["model_request"]["messages"]
        system_prompt = messages[0]["content"]
        user_prompt = ""
        input_ref_ids = [r["refImageId"] for r in assembled["ref_order"]]
        content = messages[1]["content"]
        if isinstance(content, str):
            user_prompt = content
        else:
            user_prompt = "\n".join(
                p.get("text", "") for p in content if p.get("type") == "text"
            )
        snapshot = _rules_snapshot(assembled["loaded_rules"])

        try:
            cfg = load_config()
            planner_model = cfg["model"]
            raw = run_planner(messages, config=cfg)
            parsed = parse_plan_output(raw)
        except PlannerError as exc:
            run_id = _insert_plan_run(
                conn,
                plan_id=plan_id,
                status="failed",
                planner_model="",
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                input_ref_ids=input_ref_ids,
                rules_snapshot=snapshot,
                raw_output=exc.raw_output,
                error=str(exc),
            )
            row = _get_run(conn, run_id)
            return _run_row_to_out(row)

        run_id = _insert_plan_run(
            conn,
            plan_id=plan_id,
            status="success",
            planner_model=planner_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            input_ref_ids=input_ref_ids,
            rules_snapshot=snapshot,
            raw_output=raw,
            design_notes=parsed["designNotes"],
            open_questions=parsed["openQuestions"],
            generated_prompt=parsed["prompt"],
            ref_usage_notes=parsed["refUsageNotes"],
        )
        row = _get_run(conn, run_id)
        return _run_row_to_out(row)


@router.post("/plans/{plan_id}/adopt", response_model=ImagePlanOut)
def adopt_plan_run(body: AdoptRunRequest, plan_id: str = PathParam()) -> ImagePlanOut:
    with connect() as conn:
        plan = conn.execute(
            "SELECT * FROM image_plans WHERE id = ?", (plan_id,)
        ).fetchone()
        if not plan:
            raise HTTPException(404, "plan not found")
        if plan["status"] != "draft":
            raise HTTPException(409, "only draft plans can adopt")
        run = _get_run(conn, body.runId)
        if not run or run["plan_id"] != plan_id:
            raise HTTPException(404, "run not found for plan")
        if run["status"] != "success":
            raise HTTPException(422, "only successful runs can be adopted")
        if not (run["generated_prompt"] or "").strip():
            raise HTTPException(422, "run has no generated prompt")

        ts = now_iso()
        conn.execute(
            """
            UPDATE image_plans
            SET prompt = ?, design_notes = ?, open_questions = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                run["generated_prompt"],
                run["design_notes"] or "",
                run["open_questions"] or "[]",
                ts,
                plan_id,
            ),
        )
        conn.execute(
            "UPDATE plan_runs SET adopted_at = ? WHERE id = ?", (ts, body.runId)
        )
        row = conn.execute(
            "SELECT * FROM image_plans WHERE id = ?", (plan_id,)
        ).fetchone()
        return _plan_row_to_out(row)
