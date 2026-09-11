from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import Image
import io

from .. import db
from ..deps import STORE_SCOPED_ROLES, require_roles
from ..services import media_service

router = APIRouter()
_ALL = require_roles("master", "shopping", "lojista", "gestor", "vendedor")
_UPLOADER = require_roles("master", "shopping", "lojista", "gestor")

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/jpg",
    "image/pjpeg",
    "image/png",
    "image/webp",
}
MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB


@router.post("/vehicles/upload-photos")
async def upload_vehicle_photos(
    files: list[UploadFile] | None = File(None),
    file: UploadFile | None = File(None),
    user: dict = Depends(_UPLOADER),
):
    upload_list: list[UploadFile] = []
    if files:
        upload_list.extend(files)
    if file:
        upload_list.append(file)
    if not upload_list:
        raise HTTPException(400, "Nenhum arquivo enviado")

    uploaded_photos = []

    for uploaded_file in upload_list:
        if uploaded_file.content_type and uploaded_file.content_type.lower() not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                415,
                f"Tipo de arquivo não suportado ({uploaded_file.content_type}). Envie JPEG, PNG ou WEBP.",
            )

        content = await uploaded_file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                413,
                f"Arquivo '{uploaded_file.filename or 'enviado'}' excede o limite máximo permitido de 15MB.",
            )

        try:
            with Image.open(io.BytesIO(content)) as img:
                if img.format not in ("JPEG", "PNG", "WEBP"):
                    raise HTTPException(
                        415,
                        f"Formato de imagem '{img.format}' não suportado. Envie JPEG, PNG ou WEBP.",
                    )
                orig_width, orig_height = img.size
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(415, "Arquivo corrompido ou formato de imagem inválido.")

        hash_md5 = media_service.compute_md5(content)
        variants = media_service.generate_image_variants(content)
        meta = media_service.upload_variants_to_r2(variants, hash_md5)

        meta.update({
            "size_bytes": len(content),
            "original_width": orig_width,
            "original_height": orig_height,
            "width": 1200,
            "height": 900,
        })
        uploaded_photos.append(meta)

    return {
        "photos": uploaded_photos,
        "uploaded": uploaded_photos,
    }


import json
import uuid
import re


def _format_vehicle_row(v: dict) -> dict:
    """Normaliza arrays, JSON e flags booleanas do veículo para o frontend."""
    # 1. Galeria de fotos (pictures)
    pics = v.get("pictures")
    if isinstance(pics, str):
        try:
            v["pictures"] = json.loads(pics)
        except Exception:
            v["pictures"] = []
    elif pics is None:
        v["pictures"] = []

    # 2. Opcionais (item_list)
    items = v.get("item_list")
    if isinstance(items, str):
        try:
            v["item_list"] = json.loads(items)
        except Exception:
            v["item_list"] = [i.strip() for i in items.split(",") if i.strip()]
    elif items is None:
        v["item_list"] = []

    # 3. Flags booleanas
    for flag in ("active", "sold", "featured", "new_vehicle", "shielded", "in_transit"):
        if flag in v and v[flag] is not None:
            v[flag] = bool(v[flag])

    return v


def _scope(user: dict) -> tuple[str, list]:
    if user["role"] in STORE_SCOPED_ROLES:
        return "WHERE v.store_id = ?", [user["store_id"]]
    return "", []


@router.get("/vehicles")
def list_vehicles(user: dict = Depends(_ALL)):
    where, params = _scope(user)
    with db.tx() as conn:
        rows = conn.execute(
            f"""
            SELECT v.*, s.name AS store_name
            FROM vehicles v JOIN stores s ON s.id = v.store_id
            {where}
            ORDER BY v.created_at DESC
            """,
            params,
        ).fetchall()
    return {"vehicles": [_format_vehicle_row(dict(r)) for r in rows]}


@router.get("/vehicles/{vid}")
def get_vehicle(vid: int, user: dict = Depends(_ALL)):
    with db.tx() as conn:
        row = conn.execute(
            "SELECT v.*, s.name AS store_name FROM vehicles v JOIN stores s ON s.id = v.store_id WHERE v.id = ?",
            (vid,),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Veículo não encontrado")
    if user["role"] in STORE_SCOPED_ROLES and row["store_id"] != user.get("store_id"):
        raise HTTPException(403, "Veículo de outra loja")
    return {"vehicle": _format_vehicle_row(dict(row))}


_REQUIRED = {"name", "price", "store_id"}
_ALL_COLUMNS = (
    "store_id", "store", "identifier", "name", "brand", "model", "version", "category",
    "kind", "doors", "color", "plate", "unit_id", "fabrication_year", "model_year",
    "price", "km", "mileage", "transmission", "exchange", "fuel", "fuel_text",
    "status", "active", "sold", "featured", "new_vehicle", "shielded", "in_transit",
    "item_list", "note", "image_path", "main_image", "pictures",
)
_PATCHABLE = {
    "name", "price", "mileage", "transmission", "fuel", "image_path", "status", "store_id",
    "brand", "model", "version", "category", "kind", "doors", "color", "plate", "unit_id",
    "fabrication_year", "model_year", "km", "exchange", "fuel_text",
    "active", "sold", "featured", "new_vehicle", "shielded", "in_transit",
    "item_list", "note", "main_image", "pictures", "store",
}


def _sync_vehicle_data(data: dict) -> None:
    """Sincroniza pares de campos compatíveis (km/mileage, transmission/exchange, etc)."""
    # 1. KM <-> Mileage
    if data.get("km") is not None and not data.get("mileage"):
        try:
            data["mileage"] = f"{int(data['km']):,} km".replace(",", ".")
        except (ValueError, TypeError):
            pass
    elif data.get("mileage") and data.get("km") is None:
        digits = re.sub(r"[^\d]", "", str(data["mileage"]))
        if digits:
            data["km"] = int(digits)

    # 2. Câmbio (transmission <-> exchange)
    if data.get("transmission") and not data.get("exchange"):
        data["exchange"] = data["transmission"]
    elif data.get("exchange") and not data.get("transmission"):
        data["transmission"] = data["exchange"]

    # 3. Combustível (fuel <-> fuel_text)
    if data.get("fuel") and not data.get("fuel_text"):
        data["fuel_text"] = data["fuel"]
    elif data.get("fuel_text") and not data.get("fuel"):
        data["fuel"] = data["fuel_text"]

    # 4. Imagem principal (image_path <-> main_image)
    if data.get("image_path") and not data.get("main_image"):
        data["main_image"] = data["image_path"]
    elif data.get("main_image") and not data.get("image_path"):
        data["image_path"] = data["main_image"]

    # 5. Se houver pictures e não houver capa, usa a primeira foto da galeria
    if isinstance(data.get("pictures"), list) and data["pictures"] and not data.get("image_path"):
        first_pic = data["pictures"][0]
        url = first_pic.get("remote_image_url") if isinstance(first_pic, dict) else str(first_pic)
        if url:
            data["image_path"] = url
            data["main_image"] = url

    # 6. Serialização JSON para arrays
    if isinstance(data.get("pictures"), list):
        data["pictures"] = json.dumps(data["pictures"], ensure_ascii=False)
    if isinstance(data.get("item_list"), list):
        data["item_list"] = json.dumps(data["item_list"], ensure_ascii=False)

    # 7. Flags booleanas para inteiros no SQLite
    for flag in ("active", "sold", "featured", "new_vehicle", "shielded", "in_transit"):
        if flag in data and data[flag] is not None:
            data[flag] = 1 if data[flag] else 0


@router.post("/vehicles", status_code=201)
def create_vehicle(payload: dict, user: dict = Depends(_ALL)):
    if user["role"] in STORE_SCOPED_ROLES:
        payload["store_id"] = user["store_id"]

    missing = [k for k in _REQUIRED if not payload.get(k)]
    if missing:
        raise HTTPException(400, f"Campos obrigatórios: {', '.join(missing)}")

    with db.tx() as conn:
        # Preenche o nome da loja se não fornecido
        if not payload.get("store") and payload.get("store_id"):
            st = conn.execute("SELECT name FROM stores WHERE id = ?", (payload["store_id"],)).fetchone()
            if st:
                payload["store"] = st["name"]

        # Gera identificador se ausente
        if not payload.get("identifier"):
            payload["identifier"] = f"Trinix-Auto-id{uuid.uuid4().hex[:8]}"

        # Padrões para flags
        payload.setdefault("status", "Publicado")
        payload.setdefault("active", 1)
        payload.setdefault("sold", 0)
        payload.setdefault("featured", 0)
        payload.setdefault("new_vehicle", 0)
        payload.setdefault("shielded", 0)
        payload.setdefault("in_transit", 0)

        _sync_vehicle_data(payload)

        # Monta INSERT dinâmico com colunas presentes
        cols = [c for c in _ALL_COLUMNS if c in payload and payload[c] is not None]
        cols_str = ", ".join(cols)
        placeholders = ", ".join("?" * len(cols))
        values = [payload[c] for c in cols]

        cur = conn.execute(f"INSERT INTO vehicles ({cols_str}) VALUES ({placeholders})", values)
        row = conn.execute(
            "SELECT v.*, s.name AS store_name FROM vehicles v JOIN stores s ON s.id = v.store_id WHERE v.id = ?",
            (cur.lastrowid,),
        ).fetchone()

    return {"vehicle": _format_vehicle_row(dict(row))}


@router.patch("/vehicles/{vid}")
def update_vehicle(vid: int, payload: dict, user: dict = Depends(_ALL)):
    if user["role"] in STORE_SCOPED_ROLES:
        payload.pop("store_id", None)
        payload.pop("store", None)

    with db.tx() as conn:
        row = conn.execute("SELECT store_id FROM vehicles WHERE id = ?", (vid,)).fetchone()
        if not row:
            raise HTTPException(404, "Veículo não encontrado")
        if user["role"] in STORE_SCOPED_ROLES and row["store_id"] != user.get("store_id"):
            raise HTTPException(403, "Veículo de outra loja")

        # Se mudou store_id por gestor/master, atualiza o nome store
        if "store_id" in payload and not payload.get("store"):
            st = conn.execute("SELECT name FROM stores WHERE id = ?", (payload["store_id"],)).fetchone()
            if st:
                payload["store"] = st["name"]

        _sync_vehicle_data(payload)

        updates = {k: v for k, v in payload.items() if k in _PATCHABLE}
        if not updates:
            raise HTTPException(400, "Nada a atualizar")

        cols = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE vehicles SET {cols}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            [*updates.values(), vid],
        )
        out = conn.execute(
            "SELECT v.*, s.name AS store_name FROM vehicles v JOIN stores s ON s.id = v.store_id WHERE v.id = ?",
            (vid,),
        ).fetchone()

    return {"vehicle": _format_vehicle_row(dict(out))}


@router.delete("/vehicles/{vid}", status_code=204)
def delete_vehicle(vid: int, user: dict = Depends(_ALL)):
    with db.tx() as conn:
        row = conn.execute("SELECT store_id FROM vehicles WHERE id = ?", (vid,)).fetchone()
        if row and user["role"] in STORE_SCOPED_ROLES and row["store_id"] != user.get("store_id"):
            raise HTTPException(403, "Veículo de outra loja")
        conn.execute("DELETE FROM vehicles WHERE id = ?", (vid,))
    return None
