"""Shared test fixtures for the issue handler test suite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def issue_opened_payload() -> dict[str, Any]:
    """Sample payload for issues.opened event."""
    return json.loads((FIXTURES_DIR / "issue_opened.json").read_text())


@pytest.fixture
def issue_edited_payload() -> dict[str, Any]:
    """Sample payload for issues.edited event."""
    return json.loads((FIXTURES_DIR / "issue_edited.json").read_text())


@pytest.fixture
def issue_comment_payload() -> dict[str, Any]:
    """Sample payload for issue_comment.created event."""
    return json.loads((FIXTURES_DIR / "issue_comment_created.json").read_text())


@pytest.fixture
def discussion_payload() -> dict[str, Any]:
    """Sample payload for discussion.created event."""
    return json.loads((FIXTURES_DIR / "discussion_created.json").read_text())


@pytest.fixture
def mock_github_client() -> AsyncMock:
    """Mock GitHub client with all methods stubbed."""
    client = AsyncMock()
    client.add_labels = AsyncMock(return_value=None)
    client.post_comment = AsyncMock(return_value=None)
    client.close_issue = AsyncMock(return_value=None)
    client.search_issues_by_author = AsyncMock(return_value=0)
    client.get_issue_state = AsyncMock(return_value="open")
    return client


@pytest.fixture
def mock_ai_client() -> AsyncMock:
    """Mock AI client for classification."""
    client = AsyncMock()
    client.classify = AsyncMock(
        return_value={
            "category": "bug",
            "confidence": 0.92,
            "reasoning": "User describes a crash with steps to reproduce.",
            "is_clear_bug": True,
        }
    )
    return client
