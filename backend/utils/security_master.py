import os
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

import requests
from loguru import logger
from zipfile import ZipFile, BadZipFile
import argparse


DEFAULT_URL = "https://directlink.icicidirect.com/NewSecurityMaster/SecurityMaster.zip"


def ensure_directory(path: Path) -> None:
    """Create directory if it does not exist."""
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)


def download_file(url: str, download_to: Path, timeout_connect_sec: int = 15, timeout_read_sec: int = 300) -> Path:
    """Download a file via HTTP streaming to the specified directory.

    Returns the path to the downloaded file.
    """
    ensure_directory(download_to)
    temp_file = Path(tempfile.mkstemp(prefix="security_master_", suffix=".zip", dir=str(download_to))[1])

    logger.info("Starting download: {}", url)
    try:
        with requests.get(url, stream=True, timeout=(timeout_connect_sec, timeout_read_sec)) as response:
            response.raise_for_status()
            total_bytes = int(response.headers.get("Content-Length", 0)) or None
            downloaded = 0
            chunk_size = 1024 * 1024
            with open(temp_file, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_bytes:
                            percent = (downloaded / total_bytes) * 100
                            if percent % 10 < (chunk_size / max(total_bytes, 1)) * 100:
                                logger.debug("Downloaded ~{:.1f}%", percent)
        logger.info("Download completed: {} ({} bytes)", temp_file, temp_file.stat().st_size)
        return temp_file
    except Exception:
        # Cleanup partial file on failure
        try:
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)
        except Exception:
            pass
        raise


def extract_zip(zip_path: Path, extract_to: Path) -> List[Path]:
    """Extract a .zip archive into the target directory and return list of extracted file paths."""
    ensure_directory(extract_to)
    extracted_files: List[Path] = []
    try:
        with ZipFile(zip_path, "r") as zf:
            members = zf.namelist()
            logger.info("Archive contains {} files", len(members))
            zf.extractall(path=extract_to)
            for member in members:
                extracted_files.append(extract_to / member)
        logger.info("Extraction completed to {}", extract_to)
    except BadZipFile as e:
        logger.error("Failed to read zip archive: {}", e)
        raise
    return extracted_files


def download_and_extract_security_master(
    destination_dir: Path,
    url: str = DEFAULT_URL,
) -> List[Path]:
    """Download the ICICI SecurityMaster zip and extract its contents into destination_dir.

    Returns a list of extracted file paths.
    """
    ensure_directory(destination_dir)
    temp_zip: Optional[Path] = None
    try:
        temp_zip = download_file(url=url, download_to=destination_dir)
        extracted = extract_zip(zip_path=temp_zip, extract_to=destination_dir)
        expected_files = {
            "CDNSEScripMaster.txt",
            "FOBSEScripMaster.txt",
            "FONSEScripMaster.txt",
            "NSEScripMaster.txt",
            "BSEScripMaster.txt",
        }
        present = {p.name for p in extracted}
        missing = sorted(list(expected_files - present))
        if missing:
            logger.warning("Missing expected files after extraction: {}", ", ".join(missing))
        else:
            logger.info("All expected files are present.")
        return extracted
    finally:
        try:
            if temp_zip and temp_zip.exists():
                temp_zip.unlink(missing_ok=True)
        except Exception:
            # Not fatal if cleanup fails
            pass


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Download and extract ICICI SecurityMaster")
    parser.add_argument(
        "--dest",
        type=str,
        default=str(Path.cwd() / "SecurityMaster"),
        help="Destination directory to place extracted .txt files",
    )
    parser.add_argument(
        "--url",
        type=str,
        default=DEFAULT_URL,
        help="Override the SecurityMaster.zip URL",
    )
    args = parser.parse_args(argv)

    destination_dir = Path(args.dest).expanduser().resolve()
    logger.info("Destination directory: {}", destination_dir)

    try:
        extracted = download_and_extract_security_master(destination_dir=destination_dir, url=args.url)
        for p in extracted:
            logger.info("Extracted: {}", p)
        return 0
    except Exception as e:
        logger.exception("Failed to download or extract SecurityMaster: {}", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())


