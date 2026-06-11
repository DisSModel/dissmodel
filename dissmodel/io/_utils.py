from __future__ import annotations

import hashlib
import pathlib

 

import io

 


VECTOR_EXTENSIONS  = {".shp", ".gpkg", ".geojson", ".json", ".zip"}
RASTER_EXTENSIONS  = {".tif", ".tiff"}
XARRAY_EXTENSIONS  = {".zarr", ".nc", ".nc4"}


def detect_format(uri: str) -> str:
    """
    Infer dataset format from URI extension.
    Raises ValueError if extension is not recognized.
    """
    path = uri.split("?")[0]   # strip query string
    ext  = pathlib.Path(path).suffix.lower()

    if ext in VECTOR_EXTENSIONS:
        return "vector"
    if ext in RASTER_EXTENSIONS:
        return "raster"
    if ext in XARRAY_EXTENSIONS:
        return "xarray"

    raise ValueError(
        f"Cannot detect format from extension '{ext}' in URI: {uri}\n"
        f"Supported: "
        f"vector {sorted(VECTOR_EXTENSIONS)}, "
        f"raster {sorted(RASTER_EXTENSIONS)}, "
        f"xarray {sorted(XARRAY_EXTENSIONS)}"
    )


def sha256_bytes(data: bytes) -> str:
    """Return sha256 hex digest of bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    """Return sha256 hex digest of a local file using chunked reads."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve_uri(uri: str, minio_client=None) -> tuple[bytes, str]:
    """
    Fetch raw bytes from any URI.
    Returns (content_bytes, sha256_checksum).

    Supported schemes:
        s3://bucket/key     — MinIO / S3
        http(s)://...       — HTTP download
        /local/path         — local file
    """
    if uri.startswith("s3://"):
        if minio_client is None:
            from dissmodel.io._storage import get_default_client
            minio_client = get_default_client()
        bucket, key = uri[5:].split("/", 1)
        obj         = minio_client.get_object(bucket, key)
        content     = obj.read()
        return content, sha256_bytes(content)

    if uri.startswith("http://") or uri.startswith("https://"):
        import urllib.request
        with urllib.request.urlopen(uri) as r:
            content = r.read()
        return content, sha256_bytes(content)

    # Local path
    with open(uri, "rb") as f:
        content = f.read()
    return content, sha256_bytes(content)

# ── leitura genérica ──────────────────────────────────────────────────────────
 
def read_bytes(uri: str) -> bytes:
    """
    Lê qualquer URI como bytes. minio_client resolvido internamente via settings.
 
    Suporta s3://, http(s)://, path local.
    Não retorna checksum — use resolve_uri() quando precisar auditar.
    """
    content, _ = resolve_uri(uri, _get_client_if_needed(uri))
    return content
 
 
def read_text(uri: str, encoding: str = "utf-8") -> str:
    """Atalho: read_bytes() decodificado. Para TOML, CSV, MD."""
    return read_bytes(uri).decode(encoding)
 
 
# ── escrita genérica ──────────────────────────────────────────────────────────
 
def write_bytes(
    data:         bytes | io.IOBase,
    uri:          str,
    content_type: str = "application/octet-stream",
) -> str:
    """
    Escreve bytes em qualquer URI. Retorna sha256 do conteúdo gravado.
 
    minio_client resolvido internamente — executor não precisa saber.
    Aceita bytes ou file-like (BytesIO, etc).
 
    Exemplos
    --------
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=150)
    checksum = write_bytes(buf, "s3://bucket/scatter.png", "image/png")
    """
    raw: bytes
    if isinstance(data, (io.RawIOBase, io.BufferedIOBase, io.BytesIO)):
        data.seek(0)
        raw = data.read() or b""
    elif isinstance(data, bytes):
        raw = data
    else:
        # Remaining io.IOBase subclasses (e.g. text streams) carry str,
        # not bytes, and cannot be written as binary content.
        raise TypeError(
            "write_bytes expects bytes or a binary stream, "
            f"got {type(data).__name__}"
        )
 
    return _write_raw(raw, uri, content_type)
 
 
def write_text(
    data:         str,
    uri:          str,
    encoding:     str = "utf-8",
    content_type: str = "text/plain",
) -> str:
    """
    Escreve str em qualquer URI. Retorna sha256 do conteúdo gravado.
 
    Separado de write_bytes — evita ambiguidade na chamada e
    deixa a intenção explícita no código do executor.
 
    Exemplos
    --------
    checksum = write_text(report_md, "s3://bucket/report.md", content_type="text/markdown")
    checksum = write_text(df.to_csv(), "./outputs/results.csv", content_type="text/csv")
    """
    return _write_raw(data.encode(encoding), uri, content_type)
 
 
# ── helpers internos ──────────────────────────────────────────────────────────
 
def _write_raw(raw: bytes, uri: str, content_type: str) -> str:
    """Escrita efetiva — não exposta ao executor."""
    checksum = sha256_bytes(raw)
 
    if uri.startswith("s3://"):
        client        = _get_client_if_needed(uri)
        bucket, key   = uri[5:].split("/", 1)
        client.put_object(
            bucket_name  = bucket,
            object_name  = key,
            data         = io.BytesIO(raw),
            length       = len(raw),
            content_type = content_type,
        )
    else:
        path = pathlib.Path(uri)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
 
    return checksum
 
 
def _get_client_if_needed(uri: str):
    """Retorna minio_client só se a URI for s3://. Evita import desnecessário."""
    if uri.startswith("s3://"):
        from dissmodel.io._storage import get_default_client
        return get_default_client()
    return None