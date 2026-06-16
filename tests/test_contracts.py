"""Tests for Shadow Kit contract enforcement system."""

import pytest

from shadow_kit.contracts import (
    ActionDeferralGuard,
    CompletionIntegrity,
    Contract,
    ContractContext,
    DangerousPathGuard,
    GitPushTargetGuard,
    LoopTripwire,
    PreDenialGate,
    ReadBeforeEdit,
    TopicOverrunGuard,
    VerifyBeforePush,
    Violation,
    check_all_post,
    check_all_pre,
    get_contract,
    get_governor,
    list_contracts,
    register_contract,
)


# ---------------------------------------------------------------------------
# VerifyBeforePush
# ---------------------------------------------------------------------------


class TestVerifyBeforePush:
    def setup_method(self):
        self.contract = VerifyBeforePush()

    def test_blocks_push_without_verification(self):
        ctx = ContractContext(
            action="git_push",
            files_edited=["src/main.py"],
            response_text="Fixed the bug. Done.",
        )
        v = self.contract.check_pre(ctx)
        assert v is not None
        assert v.severity == "block"

    def test_allows_push_with_verification_output(self):
        ctx = ContractContext(
            action="git_push",
            files_edited=["src/main.py"],
            verification_output="12 passed, 0 failed",
        )
        v = self.contract.check_pre(ctx)
        assert v is None

    def test_allows_push_with_test_markers_in_response(self):
        ctx = ContractContext(
            action="git_push",
            files_edited=["src/main.py"],
            response_text="Tests: 5 passed\nAll good.",
        )
        v = self.contract.check_pre(ctx)
        assert v is None

    def test_skips_non_push_actions(self):
        ctx = ContractContext(
            action="respond",
            files_edited=["src/main.py"],
        )
        v = self.contract.check_pre(ctx)
        assert v is None

    def test_skips_docs_only_push(self):
        ctx = ContractContext(
            action="git_push",
            files_edited=[],
        )
        v = self.contract.check_pre(ctx)
        assert v is None

    def test_traceback_counts_as_verification(self):
        ctx = ContractContext(
            action="git_push",
            files_edited=["src/main.py"],
            response_text="Traceback (most recent call last):\n  File ...",
        )
        v = self.contract.check_pre(ctx)
        assert v is None


# ---------------------------------------------------------------------------
# PreDenialGate
# ---------------------------------------------------------------------------


class TestPreDenialGate:
    def setup_method(self):
        self.contract = PreDenialGate()

    def test_blocks_denial_without_smoke_test(self):
        ctx = ContractContext(
            action="respond",
            response_text="I can't access the database from here.",
            tool_calls=[],
        )
        v = self.contract.check_post(ctx)
        assert v is not None
        assert v.severity == "block"

    def test_allows_denial_after_smoke_test(self):
        ctx = ContractContext(
            action="respond",
            response_text="I can't access the database.",
            smoke_test_ran=True,
        )
        v = self.contract.check_post(ctx)
        assert v is None

    def test_allows_denial_when_tools_called(self):
        ctx = ContractContext(
            action="respond",
            response_text="I can't access the endpoint.",
            tool_calls=["run_query"],
        )
        v = self.contract.check_post(ctx)
        assert v is None

    def test_no_false_positive_on_normal_response(self):
        ctx = ContractContext(
            action="respond",
            response_text="Here are the results from the database query.",
        )
        v = self.contract.check_post(ctx)
        assert v is None

    def test_ignores_non_respond_action(self):
        ctx = ContractContext(
            action="git_push",
            response_text="I can't access the repo.",
        )
        v = self.contract.check_post(ctx)
        assert v is None

    def test_allows_denial_with_error_output(self):
        ctx = ContractContext(
            action="respond",
            response_text="I can't access the API.\n```\nError: connection refused\n```",
        )
        v = self.contract.check_post(ctx)
        assert v is None


# ---------------------------------------------------------------------------
# LoopTripwire
# ---------------------------------------------------------------------------


class TestLoopTripwire:
    def setup_method(self):
        self.contract = LoopTripwire()

    def test_warns_on_3rd_commit(self):
        ctx = ContractContext(
            action="git_push",
            commits_this_session={"src/main.py": 3},
        )
        v = self.contract.check_pre(ctx)
        assert v is not None
        assert v.severity == "warn"

    def test_blocks_on_4th_commit(self):
        ctx = ContractContext(
            action="git_push",
            commits_this_session={"src/main.py": 4},
        )
        v = self.contract.check_pre(ctx)
        assert v is not None
        assert v.severity == "block"

    def test_no_violation_under_threshold(self):
        ctx = ContractContext(
            action="git_push",
            commits_this_session={"src/main.py": 2},
        )
        v = self.contract.check_pre(ctx)
        assert v is None


# ---------------------------------------------------------------------------
# ReadBeforeEdit
# ---------------------------------------------------------------------------


class TestReadBeforeEdit:
    def setup_method(self):
        self.contract = ReadBeforeEdit()

    def test_warns_on_edit_without_read(self):
        ctx = ContractContext(
            action="edit_file",
            files_edited=["src/main.py"],
            files_read=[],
        )
        v = self.contract.check_pre(ctx)
        assert v is not None

    def test_allows_edit_after_read(self):
        ctx = ContractContext(
            action="edit_file",
            files_edited=["src/main.py"],
            files_read=["src/main.py"],
        )
        v = self.contract.check_pre(ctx)
        assert v is None


# ---------------------------------------------------------------------------
# ActionDeferralGuard
# ---------------------------------------------------------------------------


class TestActionDeferralGuard:
    def setup_method(self):
        self.contract = ActionDeferralGuard()

    def test_blocks_proposal_without_execution(self):
        ctx = ContractContext(
            action="respond",
            response_text=(
                "Here's the approach I'd take:\n"
                "Would you like me to set up the database?\n"
                "I can configure the connection pool."
            ),
            tool_calls=[],
        )
        v = self.contract.check_post(ctx)
        assert v is not None
        assert v.severity == "block"

    def test_allows_response_with_execution_tool(self):
        ctx = ContractContext(
            action="respond",
            response_text="Would you like me to also update the config? I can set up monitoring.",
            tool_calls=["Bash"],
        )
        v = self.contract.check_post(ctx)
        assert v is None

    def test_allows_past_tense_completion(self):
        ctx = ContractContext(
            action="respond",
            response_text=(
                "Here's the approach I took:\n"
                "Step 1: Updated the config\n"
                "Done. Pushed to main."
            ),
        )
        v = self.contract.check_post(ctx)
        assert v is None

    def test_allows_brainstorm_mode(self):
        ctx = ContractContext(
            action="respond",
            response_text=(
                "Just brainstorming here:\n"
                "I can set up a queue system\n"
                "Would you like me to explore this?"
            ),
        )
        v = self.contract.check_post(ctx)
        assert v is None

    def test_allows_single_proposal_marker(self):
        ctx = ContractContext(
            action="respond",
            response_text="Would you like me to do that?",
        )
        v = self.contract.check_post(ctx)
        assert v is None


# ---------------------------------------------------------------------------
# TopicOverrunGuard
# ---------------------------------------------------------------------------


class TestTopicOverrunGuard:
    def setup_method(self):
        self.contract = TopicOverrunGuard()

    def test_warns_on_overrun(self):
        ctx = ContractContext(
            action="respond",
            response_text="Got it, understood. But also, one more thing about the config.",
        )
        v = self.contract.check_post(ctx)
        assert v is not None

    def test_allows_clean_response(self):
        ctx = ContractContext(
            action="respond",
            response_text="Done. Config updated and pushed.",
        )
        v = self.contract.check_post(ctx)
        assert v is None


# ---------------------------------------------------------------------------
# CompletionIntegrity
# ---------------------------------------------------------------------------


class TestCompletionIntegrity:
    def setup_method(self):
        self.contract = CompletionIntegrity()

    def test_blocks_done_with_gaps(self):
        ctx = ContractContext(
            action="respond",
            response_text=(
                "Everything is done.\n\n"
                "What's not done:\n"
                "- Feature B is not yet implemented\n"
                "- Feature C is still missing"
            ),
        )
        v = self.contract.check_post(ctx)
        assert v is not None
        assert v.severity == "block"

    def test_allows_done_without_gaps(self):
        ctx = ContractContext(
            action="respond",
            response_text="Everything is done. All features implemented and tested.",
        )
        v = self.contract.check_post(ctx)
        assert v is None

    def test_allows_audit_with_gaps(self):
        ctx = ContractContext(
            action="respond",
            response_text=(
                "Honest audit:\n"
                "Everything is shipped.\n"
                "But: not done, still missing some tests."
            ),
        )
        v = self.contract.check_post(ctx)
        assert v is None


# ---------------------------------------------------------------------------
# GitPushTargetGuard
# ---------------------------------------------------------------------------


class TestGitPushTargetGuard:
    def setup_method(self):
        self.contract = GitPushTargetGuard()

    def test_blocks_force_push_to_main(self):
        ctx = ContractContext(
            action="git_push",
            tool_calls=["Bash"],
            tool_params=[{"command": "git push --force origin main"}],
        )
        v = self.contract.check_pre(ctx)
        assert v is not None
        assert v.severity == "block"

    def test_warns_on_force_push_to_feature(self):
        ctx = ContractContext(
            action="git_push",
            tool_calls=["Bash"],
            tool_params=[{"command": "git push --force origin feature-branch"}],
        )
        v = self.contract.check_pre(ctx)
        assert v is not None
        assert v.severity == "warn"

    def test_allows_normal_push(self):
        ctx = ContractContext(
            action="git_push",
            tool_calls=["Bash"],
            tool_params=[{"command": "git push origin main"}],
        )
        v = self.contract.check_pre(ctx)
        assert v is None


# ---------------------------------------------------------------------------
# DangerousPathGuard
# ---------------------------------------------------------------------------


class TestDangerousPathGuard:
    def setup_method(self):
        self.contract = DangerousPathGuard()
        self.contract.project_root = "/home/user/project"

    def test_blocks_env_write(self):
        ctx = ContractContext(
            tool_calls=["Write"],
            tool_params=[{"file_path": "/home/user/project/.env"}],
        )
        v = self.contract.check_pre(ctx)
        assert v is not None
        assert v.severity == "block"

    def test_blocks_credentials_write(self):
        ctx = ContractContext(
            tool_calls=["Write"],
            tool_params=[{"file_path": "/home/user/credentials.json"}],
        )
        v = self.contract.check_pre(ctx)
        assert v is not None
        assert v.severity == "block"

    def test_warns_outside_project(self):
        ctx = ContractContext(
            tool_calls=["Write"],
            tool_params=[{"file_path": "/tmp/somefile.txt"}],
        )
        v = self.contract.check_pre(ctx)
        assert v is not None
        assert v.severity == "warn"

    def test_allows_normal_project_write(self):
        ctx = ContractContext(
            tool_calls=["Write"],
            tool_params=[{"file_path": "/home/user/project/src/main.py"}],
        )
        v = self.contract.check_pre(ctx)
        assert v is None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_list_contracts(self):
        contracts = list_contracts()
        assert len(contracts) > 0
        assert all("name" in c for c in contracts)

    def test_get_contract(self):
        c = get_contract("verify-before-push")
        assert c is not None
        assert c.name == "verify-before-push"

    def test_register_custom_contract(self):
        class Custom(Contract):
            name = "test-custom"
            failure_mode = "FM-TEST"

        register_contract(Custom())
        c = get_contract("test-custom")
        assert c is not None
        assert c.failure_mode == "FM-TEST"

    def test_check_all_pre(self):
        ctx = ContractContext(
            action="git_push",
            files_edited=["x.py"],
            response_text="Done.",
        )
        violations = check_all_pre(ctx)
        assert isinstance(violations, list)
        # Should catch verify-before-push at minimum
        names = [v.contract for v in violations]
        assert "verify-before-push" in names

    def test_check_all_post(self):
        ctx = ContractContext(
            action="respond",
            response_text="Here is your answer.",
        )
        violations = check_all_post(ctx)
        assert isinstance(violations, list)


# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------


class TestGovernance:
    def test_metrics(self):
        governor = get_governor()
        metrics = governor.get_metrics()
        assert "total_violations" in metrics
        assert "active_contracts" in metrics

    def test_hot_contracts(self):
        governor = get_governor()
        hot = governor.get_hot_contracts()
        assert isinstance(hot, list)
