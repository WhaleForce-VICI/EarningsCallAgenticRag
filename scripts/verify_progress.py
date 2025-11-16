#!/usr/bin/env python3
"""
Playwright-based smoke test for the web console run detail page.

Usage:
    python scripts/verify_progress.py --run-id 3218373a
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify run progress via Playwright")
    parser.add_argument("--run-id", required=True, help="Run identifier (e.g., 3218373a)")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Base URL of the web console (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Max wait time in seconds for progress update (default: 300)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=True,
        help="Run browser in headless mode (default: True)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target_url = f"{args.base_url}/runs/{args.run_id}"
    start = time.time()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        page = browser.new_page()
        page.goto(target_url)

        while time.time() - start < args.timeout:
            try:
                progress_text = page.text_content("#progress-label") or ""
                status_text = page.text_content("#status-label") or ""
                table_rows = page.locator("table tbody tr").count()
                if progress_text and not progress_text.startswith("0/"):
                    print(f"✅ Progress updated: {progress_text.strip()} (status={status_text.strip()})")
                    if table_rows:
                        print(f"✅ Predictions available rows={table_rows}")
                    browser.close()
                    return 0
                page.wait_for_timeout(4000)
                page.reload()
            except Exception as exc:
                print(f"⚠️  Error while checking progress: {exc}")
                page.wait_for_timeout(4000)
                page.reload()

        browser.close()
        print(f"❌ Progress did not update within {args.timeout} seconds for run {args.run_id}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
