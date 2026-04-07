#!/usr/bin/env python

import os
import sys

from app_config import AppConfig
from dotenv import load_dotenv
from run_job import run_job

def main():
    load_dotenv()
    config = AppConfig()
    run_job(config)

    return 0


if __name__ == "__main__":
    sys.exit(main())