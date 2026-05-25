"""Tests for WebhookEvent and data model parsing (T006)."""

from __future__ import annotations

from models import WebhookEvent


class TestWebhookEventFromIssueOpened:
    """Parse issues.opened event payload."""

    def test_parses_issue_opened(self, issue_opened_payload: dict) -> None:
        event = WebhookEvent.from_payload("issues", issue_opened_payload)
        assert event.event_type == "issues"
        assert event.action == "opened"
        assert event.sender_login == "community-user"
        assert event.sender_type == "User"
        assert event.author_association == "NONE"
        assert event.repo_owner == "opencloudtouch"
        assert event.repo_name == "opencloudtouch"
        assert event.issue_number == 42
        assert "firmware update" in event.title
        assert event.body is not None and len(event.body) > 0
        assert event.existing_labels == []
        assert event.is_discussion is False

    def test_parses_issue_edited(self, issue_edited_payload: dict) -> None:
        event = WebhookEvent.from_payload("issues", issue_edited_payload)
        assert event.action == "edited"
        assert "[EDITED]" in event.title

    def test_empty_body_normalized(self, issue_opened_payload: dict) -> None:
        issue_opened_payload["issue"]["body"] = None
        event = WebhookEvent.from_payload("issues", issue_opened_payload)
        assert event.body == ""

    def test_labels_extracted(self, issue_opened_payload: dict) -> None:
        issue_opened_payload["issue"]["labels"] = [
            {"name": "bug"},
            {"name": "needs-triage"},
        ]
        event = WebhookEvent.from_payload("issues", issue_opened_payload)
        assert event.existing_labels == ["bug", "needs-triage"]


class TestWebhookEventFromComment:
    """Parse issue_comment.created event payload."""

    def test_parses_comment_event(self, issue_comment_payload: dict) -> None:
        event = WebhookEvent.from_payload("issue_comment", issue_comment_payload)
        assert event.event_type == "issue_comment"
        assert event.action == "created"
        assert event.sender_login == "another-user"
        assert event.author_association == "NONE"
        assert event.issue_number == 42


class TestWebhookEventFromDiscussion:
    """Parse discussion.created event payload (T045)."""

    def test_parses_discussion_event(self, discussion_payload: dict) -> None:
        event = WebhookEvent.from_payload("discussion", discussion_payload)
        assert event.event_type == "discussion"
        assert event.action == "created"
        assert event.is_discussion is True
        assert event.issue_number == 10
        assert "multiple speakers" in event.title
        assert event.existing_labels == []

    def test_discussion_no_labels(self, discussion_payload: dict) -> None:
        """Discussions have no labels field in standard GitHub."""
        event = WebhookEvent.from_payload("discussion", discussion_payload)
        assert event.existing_labels == []

    def test_discussion_body_parsed(self, discussion_payload: dict) -> None:
        event = WebhookEvent.from_payload("discussion", discussion_payload)
        assert "three SoundTouch speakers" in event.body


class TestWebhookEventFromCommentExtended:
    """Extended comment event parsing tests (T047)."""

    def test_comment_extracts_parent_issue(self, issue_comment_payload: dict) -> None:
        event = WebhookEvent.from_payload("issue_comment", issue_comment_payload)
        assert event.issue_number == 42
        assert event.title == "Speaker not responding after firmware update"

    def test_comment_merges_parent_and_comment_body(self, issue_comment_payload: dict) -> None:
        """Comment events should merge parent issue body + comment body for classification context."""
        event = WebhookEvent.from_payload("issue_comment", issue_comment_payload)
        assert "Original issue body here." in event.body
        assert "I have the same problem with my SoundTouch 10" in event.body

    def test_comment_author_association(self, issue_comment_payload: dict) -> None:
        """Author association should come from comment, not parent issue."""
        event = WebhookEvent.from_payload("issue_comment", issue_comment_payload)
        assert event.author_association == "NONE"
        assert event.sender_login == "another-user"

    def test_discussion_no_labels(self, discussion_payload: dict) -> None:
        event = WebhookEvent.from_payload("discussion", discussion_payload)
        assert event.existing_labels == []
