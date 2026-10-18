"""Lectura o descarga del XLS de Shiller, sin registros por ejecución."""

from datetime import datetime, timezone
from pathlib import Path
import ssl
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import certifi


INSTRUMENT = "SHILLER_SP_COMPOSITE"
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
