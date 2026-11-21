import hashlib
import os
import re
from pathlib import Path
from typing import Protocol
from .db import DATA

def digest(value: bytes):
    return hashlib.sha256(value).hexdigest()

class Storage(Protocol):
    def put(self, data: bytes, suffix: str) -> str: ...
    def get(self, key: str) -> bytes: ...
    def healthcheck(self) -> None: ...

def validate_key(key: str):
    if not re.fullmatch(r"[0-9a-f]{64}\.(pdf|png|txt|zip)", key):
        raise ValueError("Invalid content-addressed storage key")

def object_key(data: bytes, suffix: str):
    key = digest(data) + suffix
    validate_key(key)
    return key

class LocalStorage:
    """Content-addressed, append-only storage. Caller never supplies a path."""
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, data: bytes, suffix: str):
        key = object_key(data, suffix)
        path = self.root / key
        if not path.exists():
            try:
                with path.open("xb") as f:
                    f.write(data)
            except FileExistsError:
                pass  # A concurrent identical content-addressed write won.
        if digest(path.read_bytes()) != digest(data):
            raise OSError("Stored object integrity conflict")
        return key

    def get(self, key: str):
        validate_key(key)
        path = (self.root / key).resolve()
        if path.parent != self.root:
            raise ValueError("Invalid storage key")
        return path.read_bytes()

    def healthcheck(self):
        if not self.root.is_dir() or not os.access(self.root, os.R_OK | os.W_OK):
            raise OSError("Local artifact storage is unavailable")

class AzureBlobStorage:
    """Private container, Entra identity, create-only writes, no account keys or SAS.

    Blob URLs are never returned to the browser. FastAPI authenticates downloads
    and reads bytes using its own identity. Client injection is for contract tests.
    """
    def __init__(self, account_url: str, container: str, client=None):
        from urllib.parse import urlparse
        parsed = urlparse(account_url)
        if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".blob.core.windows.net") or parsed.query or parsed.path not in {"", "/"}:
            raise ValueError("A public-Azure HTTPS Blob account endpoint is required")
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{1,61}[a-z0-9])", container):
            raise ValueError("Invalid private container name")
        if client is None:
            from azure.storage.blob import BlobServiceClient
            from .azure_auth import credential
            client = BlobServiceClient(account_url, credential=credential(),
                                       connection_timeout=5, read_timeout=15, retry_total=2)
        self.container = client.get_container_client(container)

    def put(self, data: bytes, suffix: str):
        from azure.core.exceptions import ResourceExistsError
        from azure.storage.blob import ContentSettings
        key = object_key(data, suffix)
        content_type = {".pdf": "application/pdf", ".png": "image/png", ".txt": "text/plain", ".zip": "application/zip"}[suffix]
        try:
            self.container.upload_blob(name=key, data=data, overwrite=False,
                content_settings=ContentSettings(content_type=content_type), metadata={"sha256": digest(data)})
        except ResourceExistsError:
            if digest(self.get(key)) != digest(data):
                raise OSError("Existing blob does not match the content-addressed key")
        return key

    def get(self, key: str):
        from azure.core.exceptions import ResourceNotFoundError
        validate_key(key)
        try:
            return self.container.download_blob(key).readall()
        except ResourceNotFoundError as exc:
            raise FileNotFoundError("Private artifact not found") from exc

    def healthcheck(self):
        properties = self.container.get_container_properties()
        if properties.get("public_access") is not None:
            raise OSError("Artifact container must deny anonymous access")

class VercelBlobStorage:
    """Private Vercel Blob using Vercel's Python SDK and content-addressed paths."""
    def __init__(self):
        if not os.getenv("BLOB_STORE_ID") and not os.getenv("BLOB_READ_WRITE_TOKEN") and not os.getenv("VERCEL_BLOB_READ_WRITE_TOKEN"):
            raise ValueError("Connect a private Blob store to the Vercel project")
        try:
            from vercel import blob  # noqa: F401 - validate that the runtime SDK is installed
        except ImportError as exc:
            raise RuntimeError("Install the pinned vercel-blob SDK for this deployment") from exc

    @staticmethod
    def _api():
        from vercel import blob
        return blob.sync

    def put(self, data: bytes, suffix: str):
        key = object_key(data, suffix)
        content_type = {".pdf": "application/pdf", ".png": "image/png", ".txt": "text/plain", ".zip": "application/zip"}[suffix]
        api = self._api()
        try:
            api.put_blob(key, data, access="private", content_type=content_type, allow_overwrite=False)
        except Exception as upload_error:
            # Content-addressed retries are safe: only accept a pre-existing
            # object after its full bytes match the expected digest.
            try:
                existing = self.get(key)
            except Exception:
                raise upload_error
            if digest(existing) != digest(data):
                raise OSError("Existing private Blob does not match its content-addressed key") from upload_error
        return key

    def get(self, key: str):
        validate_key(key)
        result = self._api().get_blob(key, access="private")
        data = result.body
        if digest(data) != key.split(".", 1)[0]:
            raise OSError("Private Blob integrity check failed")
        return data

    def healthcheck(self):
        # Force a private-store request so missing credentials or an inaccessible
        # store fails readiness instead of silently falling back to local disk.
        iterator = iter(self._api().query_blobs(page_size=1))
        next(iterator, None)

def build_storage():
    mode = os.getenv("STORAGE_BACKEND", "local")
    if mode == "local":
        if os.getenv("APP_ENV") == "production":
            raise ValueError("Production requires private Azure Blob Storage; local storage is development only")
        return LocalStorage(DATA / "objects")
    if mode == "azure":
        return AzureBlobStorage(os.environ["AZURE_STORAGE_ACCOUNT_URL"], os.environ["AZURE_STORAGE_CONTAINER"])
    if mode == "vercel_blob":
        if os.getenv("VERCEL") != "1":
            raise ValueError("Vercel Blob storage is supported only in the Vercel runtime")
        return VercelBlobStorage()
    raise ValueError("STORAGE_BACKEND must be local, azure, or vercel_blob; never silently fall back")

store = build_storage()
