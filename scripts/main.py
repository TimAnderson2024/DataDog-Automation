#!/usr/bin/env python

import logging
import sys

from dotenv import load_dotenv
from app_config import AppConfig
from run_job import run_job

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    load_dotenv()
    logger = logging.getLogger(__name__)

    logger.info("Gathering configuration objects...")
    config = AppConfig()
    logger.info("Configuration loaded successfully. Starting job execution...")
    run_job(config)

    return 0


if __name__ == "__main__":
    sys.exit(main())