import argparse
from pathlib import Path
from typing import Optional

from loguru import logger

from .postgres import ensure_tables, get_engine


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Create instruments table if not exists")
    _ = parser.parse_args(argv)

    engine = get_engine()
    if engine is None:
        logger.error("POSTGRES_DSN not configured; cannot create tables")
        return 1

    ensure_tables()
    logger.info("Ensured instruments and related tables exist")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


