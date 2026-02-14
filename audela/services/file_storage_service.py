from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from dataclasses import dataclass

from flask import current_app
from werkzeug.utils import secure_filename
from pathlib import Path

def delete_storage_path(tenant_id: int, storage_path: str) -> None:
    """
    Remove um arquivo/pasta do storage do tenant com segurança.
    storage_path deve ser relativo ao root do tenant (ex: "folders/f_12/abc.csv").
    """
    # Reaproveita a função já existente no seu serviço (ela já resolve para abs path no root do tenant)
    abs_path = Path(resolve_abs_path(tenant_id, storage_path)).resolve()

    # Segurança: garante que a remoção fica dentro do root do tenant
    tenant_root = Path(resolve_abs_path(tenant_id, "")).resolve()
    if abs_path != tenant_root and tenant_root not in abs_path.parents:
        raise ValueError("Unsafe delete path (outside tenant root).")

    if abs_path.is_dir():
        shutil.rmtree(abs_path, ignore_errors=True)
    elif abs_path.exists():
        abs_path.unlink()



ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls", "parquet"}


@dataclass(frozen=True)
class StoredFile:
    rel_path: str
    abs_path: str
    original_filename: str
    file_format: str
    size_bytes: int
    sha256: str


def _tenant_root(tenant_id: int) -> str:
    root = current_app.config.get("TENANT_FILE_ROOT") or os.path.join(current_app.instance_path, "tenant_files")
    return os.path.join(root, str(int(tenant_id)))


def ensure_tenant_root(tenant_id: int) -> str:
    root = _tenant_root(tenant_id)
    os.makedirs(root, exist_ok=True)
    return root


def _ext_from_filename(filename: str) -> str:
    filename = (filename or "").lower()
    if "." not in filename:
        return ""
    return filename.rsplit(".", 1)[-1]


def validate_extension(filename: str) -> str:
    ext = _ext_from_filename(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Extensão não suportada: {ext or '(vazia)'}")
    # normalize
    if ext in ("xls", "xlsx"):
        return "excel"
    return ext


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _store_upload_impl(tenant_id: int, folder_rel: str | None, file_storage) -> StoredFile:
    """Store an uploaded file under the tenant root.

    folder_rel is a relative folder path inside the tenant root (e.g. "finance/2026").
    """
    if not file_storage or not getattr(file_storage, "filename", None):
        raise ValueError("Arquivo ausente")

    original = secure_filename(file_storage.filename)
    if not original:
        raise ValueError("Nome de arquivo inválido")

    fmt = validate_extension(original)

    root = ensure_tenant_root(tenant_id)
    folder_rel = (folder_rel or "").strip().strip("/")
    abs_folder = os.path.join(root, folder_rel) if folder_rel else root
    os.makedirs(abs_folder, exist_ok=True)

    # Use a UUID filename to avoid collisions and path tricks
    ext = _ext_from_filename(original)
    suffix = ".parquet" if fmt == "parquet" else (".csv" if fmt == "csv" else (".xls" if ext == "xls" else ".xlsx"))
    fname = f"{uuid.uuid4().hex}{suffix}"
    abs_path = os.path.join(abs_folder, fname)
    file_storage.save(abs_path)

    size = os.path.getsize(abs_path)
    sha = _sha256_file(abs_path)
    rel_path = os.path.relpath(abs_path, root)

    return StoredFile(
        rel_path=rel_path,
        abs_path=abs_path,
        original_filename=original,
        file_format=fmt,
        size_bytes=size,
        sha256=sha,
    )


def store_upload(tenant_id: int, file_storage, *, folder_rel: str | None = None) -> dict:
    """Store upload (portal API).

    Portal routes expect:
      store_upload(tenant_id, file, folder_rel=...)
    and a dict return with keys: storage_path, file_format, original_filename.
    """
    stored = _store_upload_impl(tenant_id, folder_rel, file_storage)
    return {
        "storage_path": stored.rel_path,
        "abs_path": stored.abs_path,
        "original_filename": stored.original_filename,
        "file_format": stored.file_format,
        "size_bytes": stored.size_bytes,
        "sha256": stored.sha256,
    }


def store_bytes(tenant_id: int, folder_rel: str | None, filename: str, content: bytes) -> StoredFile:
    original = secure_filename(filename or "")
    if not original:
        raise ValueError("Nome de arquivo inválido")
    fmt = validate_extension(original)

    root = ensure_tenant_root(tenant_id)
    folder_rel = (folder_rel or "").strip().strip("/")
    abs_folder = os.path.join(root, folder_rel) if folder_rel else root
    os.makedirs(abs_folder, exist_ok=True)

    ext = _ext_from_filename(original)
    suffix = ".parquet" if fmt == "parquet" else (".csv" if fmt == "csv" else (".xls" if ext == "xls" else ".xlsx"))
    fname = f"{uuid.uuid4().hex}{suffix}"
    abs_path = os.path.join(abs_folder, fname)
    with open(abs_path, "wb") as f:
        f.write(content)

    size = os.path.getsize(abs_path)
    sha = _sha256_file(abs_path)
    rel_path = os.path.relpath(abs_path, root)

    return StoredFile(
        rel_path=rel_path,
        abs_path=abs_path,
        original_filename=original,
        file_format=fmt,
        size_bytes=size,
        sha256=sha,
    )


def download_from_url(
    tenant_id: int,
    url: str,
    *,
    filename_hint: str | None = None,
    folder_rel: str | None = None,
) -> dict:
    """Download a file from URL and store under tenant root."""
    import os
    import re
    import requests

    url = (url or "").strip()
    if not url:
        raise ValueError("URL inválida")

    timeout = current_app.config.get("URL_DOWNLOAD_TIMEOUT", 30)
    max_bytes = current_app.config.get("MAX_UPLOAD_BYTES") or current_app.config.get("MAX_CONTENT_LENGTH")
    if not max_bytes:
        max_bytes = 50 * 1024 * 1024  # 50MB default

    r = requests.get(url, stream=True, timeout=timeout)
    r.raise_for_status()

    filename = (filename_hint or "").strip()
    if not filename:
        cd = r.headers.get("content-disposition") or ""
        m = re.search(r'filename\*=UTF-8\'\'([^;]+)|filename="?([^";]+)"?', cd, flags=re.IGNORECASE)
        if m:
            filename = (m.group(1) or m.group(2) or "").strip()
    if not filename:
        filename = os.path.basename(url.split("?")[0].rstrip("/")) or "download.csv"

    def _iter():
        for chunk in r.iter_content(chunk_size=1024 * 1024):
            if chunk:
                yield chunk

    stored = store_stream(tenant_id, folder_rel, filename, _iter(), max_bytes=int(max_bytes))
    return {
        "storage_path": stored.rel_path,
        "abs_path": stored.abs_path,
        "original_filename": stored.original_filename,
        "file_format": stored.file_format,
        "size_bytes": stored.size_bytes,
        "sha256": stored.sha256,
    }


def download_from_s3(
    tenant_id: int,
    *,
    bucket: str,
    key: str,
    filename_hint: str | None = None,
    region: str | None = None,
    folder_rel: str | None = None,
) -> dict:
    """Download an S3 object and store under tenant root."""
    import os
    import boto3

    bucket = (bucket or "").strip()
    key = (key or "").strip().lstrip("/")
    if not bucket or not key:
        raise ValueError("Bucket e key são obrigatórios")

    max_bytes = current_app.config.get("MAX_UPLOAD_BYTES") or current_app.config.get("MAX_CONTENT_LENGTH")
    if not max_bytes:
        max_bytes = 50 * 1024 * 1024  # 50MB default

    client = boto3.client("s3", region_name=region) if region else boto3.client("s3")
    obj = client.get_object(Bucket=bucket, Key=key)
    body = obj["Body"]

    filename = (filename_hint or "").strip() or os.path.basename(key) or "s3_object.csv"

    def _iter():
        while True:
            chunk = body.read(1024 * 1024)
            if not chunk:
                break
            yield chunk

    stored = store_stream(tenant_id, folder_rel, filename, _iter(), max_bytes=int(max_bytes))
    return {
        "storage_path": stored.rel_path,
        "abs_path": stored.abs_path,
        "original_filename": stored.original_filename,
        "file_format": stored.file_format,
        "size_bytes": stored.size_bytes,
        "sha256": stored.sha256,
    }


def store_stream(
    tenant_id: int,
    folder_rel: str | None,
    filename: str,
    iter_chunks,
    *,
    max_bytes: int | None = None,
) -> StoredFile:
    """Store streamed content without loading it all in memory."""
    original = secure_filename(filename or "")
    if not original:
        raise ValueError("Nome de arquivo inválido")
    fmt = validate_extension(original)

    root = ensure_tenant_root(tenant_id)
    folder_rel = (folder_rel or "").strip().strip("/")
    abs_folder = os.path.join(root, folder_rel) if folder_rel else root
    os.makedirs(abs_folder, exist_ok=True)

    ext = _ext_from_filename(original)
    suffix = ".parquet" if fmt == "parquet" else (".csv" if fmt == "csv" else (".xls" if ext == "xls" else ".xlsx"))
    fname = f"{uuid.uuid4().hex}{suffix}"
    abs_path = os.path.join(abs_folder, fname)

    written = 0
    with open(abs_path, "wb") as f:
        for chunk in iter_chunks:
            if not chunk:
                continue
            f.write(chunk)
            written += len(chunk)
            if max_bytes and written > max_bytes:
                try:
                    os.remove(abs_path)
                except Exception:
                    pass
                raise ValueError("Arquivo excede o tamanho máximo permitido")

    size = os.path.getsize(abs_path)
    sha = _sha256_file(abs_path)
    rel_path = os.path.relpath(abs_path, root)

    return StoredFile(
        rel_path=rel_path,
        abs_path=abs_path,
        original_filename=original,
        file_format=fmt,
        size_bytes=size,
        sha256=sha,
    )


def resolve_abs_path(tenant_id: int, rel_path: str) -> str:
    root = ensure_tenant_root(tenant_id)
    # prevent path traversal
    rel_path = (rel_path or "").replace("\\", "/").lstrip("/")
    abs_path = os.path.abspath(os.path.join(root, rel_path))
    if not abs_path.startswith(os.path.abspath(root) + os.sep):
        raise ValueError("Caminho inválido")
    return abs_path


def delete_stored_file(tenant_id: int, rel_path: str) -> None:
    abs_path = resolve_abs_path(tenant_id, rel_path)
    try:
        os.remove(abs_path)
    except FileNotFoundError:
        return


def delete_folder_tree(tenant_id: int, folder_rel: str) -> None:
    root = ensure_tenant_root(tenant_id)
    folder_rel = (folder_rel or "").replace("\\", "/").strip().strip("/")
    abs_folder = os.path.abspath(os.path.join(root, folder_rel))
    if not abs_folder.startswith(os.path.abspath(root) + os.sep):
        raise ValueError("Caminho inválido")
    if os.path.isdir(abs_folder):
        shutil.rmtree(abs_folder, ignore_errors=True)
