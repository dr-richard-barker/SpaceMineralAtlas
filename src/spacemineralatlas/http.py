"""Polite, resilient HTTP fetching with on-disk caching and checksum recording.

Both NASA endpoints this project uses are public and unauthenticated, but neither
is a high-availability service. The NLSP/LSDA query API in particular returns
HTTP 502/503 within a few hundred milliseconds if requests are issued back to back
(observed repeatedly during development). Every network access in this project
therefore goes through :func:`fetch`, which:

  1. serves from an on-disk cache when possible, so a re-run costs no requests;
  2. throttles to a minimum interval between live requests;
  3. retries transient failures with exponential backoff;
  4. records a SHA-256 of every byte sequence it stores.

The checksum log is what makes the analysis auditable: ``data/raw/`` is gitignored
(the files are large and belong to NASA, not to this repository), but anyone can
re-run ``make fetch`` and confirm they received the same bytes we did.
"""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path

import requests

from .paths import CHECKSUM_FILE, FAIR

logger = logging.getLogger(__name__)

# Minimum wall-clock seconds between two live requests to the same host.
# 2.0 s was chosen empirically: at ~0.3 s the LSDA API returns 502/503 within a
# handful of requests, at 2.0 s a full 134-page harvest completes without error.
MIN_REQUEST_INTERVAL_S = 2.0

# Transient HTTP statuses worth retrying. 502/503 are what LSDA returns when
# throttling; 429 and 504 are included as the standard transient set.
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

USER_AGENT = (
    "SpaceMineralAtlas/0.1 (research; https://github.com/dr-richard-barker/SpaceMineralAtlas)"
)

_last_request_at: dict[str, float] = {}


def _throttle(host: str) -> None:
    """Sleep just long enough that we do not exceed the per-host request rate."""
    now = time.monotonic()
    previous = _last_request_at.get(host)
    if previous is not None:
        wait = MIN_REQUEST_INTERVAL_S - (now - previous)
        if wait > 0:
            time.sleep(wait)
    _last_request_at[host] = time.monotonic()


def record_checksum(path: Path, payload: bytes) -> str:
    """Append a ``<sha256>  <relative-path>`` line for *payload* and return the digest.

    Re-recording the same path replaces its previous line, so the file always
    reflects the current contents of ``data/raw/`` rather than accumulating history.
    """
    digest = hashlib.sha256(payload).hexdigest()
    FAIR.mkdir(parents=True, exist_ok=True)

    try:
        relative = path.relative_to(CHECKSUM_FILE.parents[1])
    except ValueError:
        relative = path

    lines: list[str] = []
    if CHECKSUM_FILE.exists():
        lines = [
            line
            for line in CHECKSUM_FILE.read_text().splitlines()
            if line.strip() and not line.endswith(f"  {relative}")
        ]
    lines.append(f"{digest}  {relative}")
    CHECKSUM_FILE.write_text("\n".join(sorted(lines)) + "\n")
    return digest


def fetch(
    url: str,
    cache_path: Path,
    *,
    max_retries: int = 5,
    timeout: int = 90,
    force: bool = False,
) -> bytes:
    """Return the bytes at *url*, using *cache_path* as a persistent cache.

    Parameters
    ----------
    url:
        Absolute URL to retrieve.
    cache_path:
        Where the response body is stored. If it already exists and *force* is
        False, no network request is made at all.
    max_retries:
        How many attempts to make before giving up. Backoff is ``2 ** attempt``
        seconds, so five attempts span roughly 30 s.
    force:
        Ignore any cached copy and re-download.

    Raises
    ------
    requests.HTTPError
        If every attempt failed, or the server returned a non-retryable error.
    """
    if cache_path.exists() and not force:
        logger.debug("cache hit: %s", cache_path.name)
        return cache_path.read_bytes()

    host = requests.utils.urlparse(url).netloc
    last_error: Exception | None = None

    for attempt in range(max_retries):
        _throttle(host)
        try:
            response = requests.get(
                url, timeout=timeout, headers={"User-Agent": USER_AGENT}
            )
            if response.status_code in RETRYABLE_STATUS:
                # Transient: back off and try again rather than failing the run.
                raise requests.HTTPError(
                    f"HTTP {response.status_code} (retryable) for {url}"
                )
            response.raise_for_status()

            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(response.content)
            digest = record_checksum(cache_path, response.content)
            logger.info(
                "fetched %s (%d bytes, sha256 %s...)",
                cache_path.name, len(response.content), digest[:12],
            )
            return response.content

        except Exception as error:  # noqa: BLE001 - retried and re-raised below
            last_error = error
            if attempt < max_retries - 1:
                backoff = 2 ** attempt
                logger.warning(
                    "attempt %d/%d failed (%s); retrying in %ds",
                    attempt + 1, max_retries, error, backoff,
                )
                time.sleep(backoff)

    # Deliberately fatal. An earlier version of this project (the Veggie dashboard)
    # silently substituted generated numbers when a fetch failed; that is precisely
    # the failure mode this project exists to avoid.
    raise requests.HTTPError(
        f"Could not retrieve {url} after {max_retries} attempts: {last_error}"
    )
