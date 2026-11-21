from __future__ import annotations

import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Cookie, Depends, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import BadSignature, URLSafeSerializer
from pydantic import BaseModel, Field

from app import aws_services


BASE_DIR = Path(__file__).resolve().parent
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "Admin123!")
COOKIE_SECRET = os.getenv("COOKIE_SECRET", "pc3-local-only-change-me")
serializer = URLSafeSerializer(COOKIE_SECRET, salt="pc3-admin")


class LoginRequest(BaseModel):
    username: str
    password: str


class OrderItem(BaseModel):
    product_id: str
    quantity: int = Field(ge=1, le=20)


class OrderRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=80)
    items: list[OrderItem]


def require_admin(admin_session: str | None = Cookie(default=None)) -> str:
    if not admin_session:
        raise HTTPException(status_code=401, detail="Se requiere acceso administrador")
    try:
        username = serializer.loads(admin_session)
    except BadSignature as error:
        raise HTTPException(status_code=401, detail="Sesión inválida") from error
    if username != ADMIN_USER:
        raise HTTPException(status_code=403, detail="Acceso denegado")
    return username


@asynccontextmanager
async def lifespan(_: FastAPI):
    aws_services.wait_for_resources()
    yield


app = FastAPI(title="PC3 Tienda LocalStack", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", **aws_services.service_status()}


@app.post("/api/login")
def login(payload: LoginRequest, response: Response):
    valid_user = secrets.compare_digest(payload.username, ADMIN_USER)
    valid_password = secrets.compare_digest(payload.password, ADMIN_PASSWORD)
    if not (valid_user and valid_password):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    response.set_cookie(
        "admin_session",
        serializer.dumps(ADMIN_USER),
        httponly=True,
        samesite="strict",
        secure=False,
        max_age=3600,
    )
    return {"authenticated": True, "username": ADMIN_USER}


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie("admin_session")
    return {"authenticated": False}


@app.get("/api/products")
def products():
    return aws_services.list_products()


@app.post("/api/orders", status_code=201)
def order(payload: OrderRequest):
    try:
        return aws_services.create_order(
            user_id=payload.user_id,
            requested_items=[item.model_dump() for item in payload.items],
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.get("/api/admin/orders")
def admin_orders(_: str = Depends(require_admin)):
    return aws_services.list_orders()


@app.get("/api/admin/queue")
def admin_queue(_: str = Depends(require_admin)):
    return aws_services.queue_status()


@app.post("/api/admin/users/{user_id}/image", status_code=201)
def upload_image(
    user_id: str,
    image: UploadFile = File(...),
    _: str = Depends(require_admin),
):
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Solo se aceptan imágenes")
    return aws_services.upload_user_image(
        user_id=user_id,
        file_obj=image.file,
        filename=image.filename or "image.bin",
        content_type=image.content_type,
    )
