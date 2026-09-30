from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi import Path as PathParam

from .db import UPLOAD_DIR, connect, now_iso
from .schemas import (
    FolderCreate,
    FolderOut,
    FolderUpdate,
    ProductCreate,
    ProductMove,
    ProductOut,
    ProductUpdate,
    ReferenceMeta,
    ReferenceOut,
    ReferenceReorder,
)

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
    )


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
        f = conn.execute(
            "SELECT * FROM folders WHERE id = ?", (folder_id,)
        ).fetchone()
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
        dup = conn.execute(
            "SELECT id FROM folders WHERE name = ?", (name,)
        ).fetchone()
        if dup:
            raise HTTPException(409, "folder name already exists")
        fid = _new_id("f")
        conn.execute(
            "INSERT INTO folders (id, name, created_at) VALUES (?, ?, ?)",
            (fid, name, now_iso()),
        )
        row = conn.execute(
            "SELECT * FROM folders WHERE id = ?", (fid,)
        ).fetchone()
        return _folder_row_to_out(row, 0, 0)


@router.patch("/folders/{folder_id}", response_model=FolderOut)
def rename_folder(body: FolderUpdate, folder_id: str = PathParam()) -> FolderOut:
    name = body.name.strip()
    if not name:
        raise HTTPException(422, "folder name required")
    with connect() as conn:
        f = conn.execute(
            "SELECT * FROM folders WHERE id = ?", (folder_id,)
        ).fetchone()
        if not f:
            raise HTTPException(404, "folder not found")
        dup = conn.execute(
            "SELECT id FROM folders WHERE name = ? AND id != ?",
            (name, folder_id),
        ).fetchone()
        if dup:
            raise HTTPException(409, "folder name already exists")
        conn.execute(
            "UPDATE folders SET name = ? WHERE id = ?", (name, folder_id)
        )
        row = conn.execute(
            "SELECT * FROM folders WHERE id = ?", (folder_id,)
        ).fetchone()
        pcount, rcount = _folder_counts(conn, folder_id)
        return _folder_row_to_out(row, pcount, rcount)


@router.delete("/folders/{folder_id}", status_code=204)
def delete_folder(folder_id: str = PathParam()) -> None:
    with connect() as conn:
        f = conn.execute(
            "SELECT id FROM folders WHERE id = ?", (folder_id,)
        ).fetchone()
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
        r = conn.execute(
            "SELECT * FROM products WHERE id = ?", (pid,)
        ).fetchone()
        return _product_row_to_out(r, 0, None)


@router.patch("/products/{product_id}", response_model=ProductOut)
def update_product(
    body: ProductUpdate, product_id: str = PathParam()
) -> ProductOut:
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


@router.get(
    "/products/{product_id}/references", response_model=list[ReferenceOut]
)
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
              (id, asset_id, product_id, url, source, purposes, desc, status, sort_order)
            VALUES (?, ?, ?, ?, '', '[]', '', 'success', ?)
            """,
            (rid, f"asset_{rid}", product_id, url, max_order + 1),
        )
        row = conn.execute(
            "SELECT * FROM ref_images WHERE id = ?", (rid,)
        ).fetchone()
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
        conn.execute(
            """
            UPDATE ref_images
            SET source = ?, purposes = ?, desc = ?
            WHERE id = ?
            """,
            (
                body.source,
                json.dumps(body.purposes, ensure_ascii=False),
                body.desc,
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
        conn.execute("DELETE FROM ref_images WHERE id = ?", (ref_id,))
