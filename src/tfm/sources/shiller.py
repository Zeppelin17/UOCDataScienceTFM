"""Adquisición y archivo del XLS original; sin interpretación de datos financieros."""

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import ssl
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4

import certifi


INSTRUMENT = "SHILLER_SP_COMPOSITE"
LANDING_URL = "https://shillerdata.com/"
MAX_BYTES = 10 * 1024 * 1024
XLS_SIGNATURE = bytes.fromhex("d0cf11e0a1b11ae1")


def validate_source_url(url: str) -> None:
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in {"img1.wsimg.com", "www.econ.yale.edu"}
            or parsed.username is not None or parsed.password is not None
            or parsed.port not in {None, 443} or not parsed.path.endswith("/ie_data.xls")):
        raise ValueError("Se requiere un enlace HTTPS al ie_data.xls publicado por Shiller")


def fetch_shiller(*, url: str, timeout: float = 30, file: str | Path | None = None) -> tuple[bytes, dict]:
    """Leer el XLS sin crear carpetas ni manifiestos."""
    validate_source_url(url)
    started = datetime.now(timezone.utc).isoformat()
    if file is None:
        request = Request(url, headers={"User-Agent": "UOCDataScienceTFM/0.1 (academic research)"})
        # Mantener la verificación del sistema y añadir un bundle portable de CA.
        context = ssl.create_default_context()
        context.load_verify_locations(cafile=certifi.where())
        with urlopen(request, timeout=timeout, context=context) as response:
            resolved_url = response.geturl()
            validate_source_url(resolved_url)
            content = response.read(MAX_BYTES + 1)
        acquisition = {"method": "https_download", "requested_at_utc": started,
                       "url": url, "resolved_url": resolved_url}
    else:
        path = Path(file).expanduser().resolve()
        with path.open("rb") as handle:
            content = handle.read(MAX_BYTES + 1)
        acquisition = {"method": "local_file_import", "input_path": str(path),
                       "declared_source_url": url,
                       "limitation": "El instante es de importación; la URL declarada no autentica el origen del fichero local."}
    if len(content) > MAX_BYTES or not content.startswith(XLS_SIGNATURE):
        raise ValueError("Se esperaba un Excel XLS binario de Shiller de hasta 10 MiB")
    return content, acquisition


def archive_shiller(raw_root: Path, *, url: str, timeout: float, file: str | Path | None = None) -> Path:
    """Conservar los bytes completos sin ejecutar fórmulas ni convertir el libro."""
    content, acquisition = fetch_shiller(url=url, timeout=timeout, file=file)
    identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "_" + uuid4().hex
    directory = raw_root / "shiller" / INSTRUMENT / identifier
    directory.mkdir(parents=True, exist_ok=False)
    try:
        (directory / "original.xls").write_bytes(content)
        manifest = {
            "schema_version": 1, "snapshot_id": identifier, "provider": "shiller",
            "instrument": INSTRUMENT, "frequency": "monthly", "status": "archived",
            "data_file": "original.xls", "sha256": sha256(content).hexdigest(), "bytes": len(content),
            "landing_url": LANDING_URL, "acquisition": acquisition,
            "archived_at_utc": datetime.now(timezone.utc).isoformat(),
            "meaning": "Original completo: puede contener evaluación, campos interpolados y resultados futuros. Archivado no significa validado.",
        }
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except (Exception, KeyboardInterrupt):
        shutil.rmtree(directory)
        raise
    return directory


def load_shiller_snapshot(directory: str | Path) -> tuple[bytes, bytes]:
    """Comprobar el mismo contenido que se devolverá al lector XLS."""
    directory = Path(directory).resolve()
    manifest_bytes = (directory / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if (manifest["schema_version"] != 1 or manifest["provider"] != "shiller"
            or manifest["instrument"] != INSTRUMENT or manifest["frequency"] != "monthly"
            or manifest["status"] != "archived" or manifest["data_file"] != "original.xls"):
        raise ValueError("Snapshot Shiller incompatible")
    with (directory / "original.xls").open("rb") as handle:
        content = handle.read(MAX_BYTES + 1)
    if (len(content) > MAX_BYTES or not content.startswith(XLS_SIGNATURE)
            or len(content) != manifest["bytes"] or sha256(content).hexdigest() != manifest["sha256"]):
        raise ValueError("SHA-256 o formato incorrecto: el original Shiller ha cambiado")
    return content, manifest_bytes
