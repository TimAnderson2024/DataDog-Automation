#!/usr/bin/env python

import os
import sys
import app_config

from dotenv import load_dotenv
from run_job import run_job

def main():
    load_dotenv()
    config = app_config.load_config(os.getenv("CONFIG_PATH"))
    run_job(config)

    return 0


if __name__ == "__main__":
    sys.exit(main())