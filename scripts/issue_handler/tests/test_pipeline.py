"""Tests for pipeline orchestration (T010)."""

from __future__ import annotations

import pytest

from models import PipelineDecision, WebhookEvent
from pipeline import Pipeline


def _make_event(**overrides) -> WebhookEvent:
    defaults = dict(
        event_type="issues",
        action="opened",
        sender_login="community-user",
        sender_type="User",
        author_association="NONE",
        repo_owner="scheilch",
        repo_name="opencloudtouch",
        issue_number=42,
        title="Test issue",
        body="Some body text that is long enough for testing purposes here.",
        existing_labels=[],
        is_discussion=False,
    )
    defaults.update(overrides)
    return WebhookEvent(**defaults)


class TestPipelineOrchestration:
    @pytest.mark.asyncio
    async def test_stages_execute_in_order(self) -> None:
        execution_order: list[str] = []

        async def stage_a(event, context):
            execution_order.append("a")
            return PipelineDecision(stage="stage_a", decision="pass", reason="ok", short_circuit=False)

        async def stage_b(event, context):
            execution_order.append("b")
            return PipelineDecision(stage="stage_b", decision="pass", reason="ok", short_circuit=False)

        pipeline = Pipeline()
        pipeline.add_stage("stage_a", stage_a)
        pipeline.add_stage("stage_b", stage_b)

        event = _make_event()
        decisions = await pipeline.run(event)

        assert execution_order == ["a", "b"]
        assert len(decisions) == 2

    @pytest.mark.asyncio
    async def test_short_circuit_stops_pipeline(self) -> None:
        execution_order: list[str] = []

        async def stage_a(event, context):
            execution_order.append("a")
            return PipelineDecision(stage="stage_a", decision="skip", reason="blocked", short_circuit=True)

        async def stage_b(event, context):
            execution_order.append("b")
            return PipelineDecision(stage="stage_b", decision="pass", reason="ok", short_circuit=False)

        pipeline = Pipeline()
        pipeline.add_stage("stage_a", stage_a)
        pipeline.add_stage("stage_b", stage_b)

        event = _make_event()
        decisions = await pipeline.run(event)

        assert execution_order == ["a"]
        assert len(decisions) == 1
        assert decisions[0].short_circuit is True

    @pytest.mark.asyncio
    async def test_decisions_logged_as_json(self, capsys) -> None:
        async def stage_a(event, context):
            return PipelineDecision(stage="stage_a", decision="pass", reason="ok", short_circuit=False)

        pipeline = Pipeline()
        pipeline.add_stage("stage_a", stage_a)

        event = _make_event()
        await pipeline.run(event)

        captured = capsys.readouterr()
        assert '"stage": "stage_a"' in captured.out or '"stage":"stage_a"' in captured.out

    @pytest.mark.asyncio
    async def test_context_shared_across_stages(self) -> None:
        async def stage_a(event, context):
            context["classification"] = {"category": "bug"}
            return PipelineDecision(stage="stage_a", decision="pass", reason="ok", short_circuit=False)

        async def stage_b(event, context):
            assert context["classification"]["category"] == "bug"
            return PipelineDecision(stage="stage_b", decision="act", reason="used context", short_circuit=True)

        pipeline = Pipeline()
        pipeline.add_stage("stage_a", stage_a)
        pipeline.add_stage("stage_b", stage_b)

        event = _make_event()
        decisions = await pipeline.run(event)
        assert len(decisions) == 2


class TestEditEventHandling:
    """Tests for issues.edited guard (T043/T044)."""

    @pytest.mark.asyncio
    async def test_edited_with_maintainer_label_skips(self) -> None:
        """If maintainer already applied a classification label, skip re-classification."""
        from pipeline import should_skip_edited_event

        event = _make_event(action="edited", existing_labels=["bug"])
        assert should_skip_edited_event(event) is True

    @pytest.mark.asyncio
    async def test_edited_without_classification_label_reclassifies(self) -> None:
        from pipeline import should_skip_edited_event

        event = _make_event(action="edited", existing_labels=["help wanted"])
        assert should_skip_edited_event(event) is False

    @pytest.mark.asyncio
    async def test_opened_event_never_skipped(self) -> None:
        from pipeline import should_skip_edited_event

        event = _make_event(action="opened", existing_labels=["bug"])
        assert should_skip_edited_event(event) is False

    @pytest.mark.asyncio
    async def test_pipeline_skips_edited_with_label(self) -> None:
        """Pipeline.run() must short-circuit for edited events with classification labels."""
        executed = []

        async def stage_a(event, context):
            executed.append("a")
            return PipelineDecision(stage="stage_a", decision="pass", reason="ok", short_circuit=False)

        pipeline = Pipeline()
        pipeline.add_stage("stage_a", stage_a)

        event = _make_event(action="edited", existing_labels=["bug"])
        decisions = await pipeline.run(event)

        assert executed == []  # no stage should have run
        assert len(decisions) == 1
        assert decisions[0].stage == "edit_guard"
        assert decisions[0].short_circuit is True
