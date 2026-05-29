#!/usr/bin/env python3
"""
run.py — entry point: test configs then push to GitHub.
Can be called directly or via cron.
"""

import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("vpn_tester.log", mode="a", encoding="utf-8"),
    ],
)

from vpn_tester import main as tester_main
from github_push import push_to_github


async def run():
    await tester_main()
    push_to_github()


if __name__ == "__main__":
    asyncio.run(run())
