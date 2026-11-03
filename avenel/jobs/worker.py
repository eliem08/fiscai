"""Background worker process for AVENEL asynchronous jobs and pipelines.

Executes in read-only container with tmpfs scratchpad for OCR and document preparation tasks.
"""

from __future__ import annotations

import logging
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("avenel.worker")


def run_worker() -> None:
    logger.info("AVENEL background worker initialized with read-only root and 512MB tmpfs scratchpad.")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Worker shutting down.")
        sys.exit(0)


if __name__ == "__main__":
    run_worker()
