"""Command line entry point of the OCT status system."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

import httpx

from oct_status.api import GitHubApi
from oct_status.labels_sync import ensure_ledger_issue, sync_labels

LABELS_SPEC = Path(__file__).resolve().parent / "labels.yml"

EXIT_OK = 0
EXIT_API_ERROR = 1
EXIT_CONFIG_ERROR = 2


class ConfigError(Exception):
    """Required configuration is missing."""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="oct_status", description="OpenCloudTouch status system")
    parser.add_argument("--labels", action="store_true", help="synchronise labels and the ledger issue")
    parser.add_argument("--dry-run", action="store_true", help="plan only, perform no writes")
    return parser


def _credentials() -> tuple[str, str]:
    token = os.environ.get("BOT_PAT") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ConfigError("missing credentials: set BOT_PAT (preferred) or GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if "/" not in repo:
        raise ConfigError("missing or invalid GITHUB_REPOSITORY (expected owner/repo)")
    return token, repo


def _emit(lines: list[str]) -> None:
    for line in lines:
        print(line)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary and lines:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("".join(f"- {line}\n" for line in lines))


async def _run_labels(api: GitHubApi, dry_run: bool) -> list[str]:
    ops = await sync_labels(api, LABELS_SPEC, dry_run=dry_run)
    ledger = await ensure_ledger_issue(api, dry_run=dry_run)
    prefix = "[dry-run] " if dry_run else ""
    return [*ops, f"{prefix}ledger issue: {'would be created' if ledger == 0 else f'#{ledger}'}"]


async def _dispatch(args: argparse.Namespace, token: str, repo: str) -> list[str]:
    api = GitHubApi(token, repo)
    try:
        if args.labels:
            return await _run_labels(api, args.dry_run)
        raise ConfigError("no mode selected (use --labels)")
    finally:
        await api.aclose()


def cli(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if not args.labels:
            raise ConfigError("no mode selected (use --labels)")
        token, repo = _credentials()
        lines = asyncio.run(_dispatch(args, token, repo))
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    except httpx.HTTPError as exc:
        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        detail = f"HTTP {status}" if status else type(exc).__name__
        print(f"error: GitHub API request failed ({detail})", file=sys.stderr)
        return EXIT_API_ERROR
    _emit(lines)
    return EXIT_OK
