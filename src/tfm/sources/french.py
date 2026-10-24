"""Original mensual de French; se conserva el ZIP sin extraer archivos a disco."""

from datetime import datetime, timezone
from pathlib import Path
import ssl
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import certifi


SOURCE_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip"
MAX_BYTES = 10 * 1024 * 1024


def validate_source_url(url: str) -> None:
    parsed = urlsplit(url)
    expected = urlsplit(SOURCE_URL)
    if (parsed.scheme != "https" or parsed.hostname != expected.hostname
            or parsed.path != expected.path or parsed.query or parsed.fragment
            or parsed.username is not None or parsed.password is not None
            or parsed.port not in {None, 443}):
        raise ValueError("Se requiere el ZIP CSV mensual de tres factores de Kenneth French")


def fetch_french(*, url: str, file: str | Path | None = None, timeout: float = 30) -> tuple[bytes, dict]:
    validate_source_url(url)
    if file is None:
        context = ssl.create_default_context()
        context.load_verify_locations(cafile=certifi.where())
        request = Request(url, headers={"User-Agent": "UOCDataScienceTFM/0.1 (academic research)"})
        with urlopen(request, timeout=timeout, context=context) as response:
            resolved = response.geturl()
            validate_source_url(resolved)
            content = response.read(MAX_BYTES + 1)
        acquisition = {"method": "https_download", "url": url, "resolved_url": resolved,
                       "requested_at_utc": datetime.now(timezone.utc).isoformat()}
    else:
        path = Path(file).expanduser().resolve()
        with path.open("rb") as handle:
            content = handle.read(MAX_BYTES + 1)
        acquisition = {"method": "local_file_import", "input_path": str(path),
                       "declared_source_url": url,
                       "limitation": "La URL declarada no autentica un archivo importado."}
    if len(content) > MAX_BYTES or not content.startswith(b"PK\x03\x04"):
        raise ValueError("Se esperaba el ZIP original de French de hasta 10 MiB")
    return content, acquisition
