"""专家邀请链接访问控制：认证中间件对规范协作前缀与历史别名同等公开。"""
import pytest

from app.middleware.auth import _is_public


# ---------- 认证中间件：规范前缀必须与历史别名同等公开 ----------


def test_collaboration_invite_prefix_is_public_get():
    assert _is_public("/api/v1/collaboration/invite/abc", "GET") is True
    assert _is_public("/api/v1/consultation/invite/abc", "GET") is True


@pytest.mark.parametrize("path", [
    "/api/v1/collaboration/task-1/messages",
    "/api/v1/collaboration/task-1/agent-history",
    "/api/v1/consultation/task-1/messages",
    "/api/v1/consultation/task-1/agent-history",
])
def test_expert_read_suffixes_are_public_get(path):
    assert _is_public(path, "GET") is True


def test_expert_inject_is_public_post():
    assert _is_public("/api/v1/collaboration/task-1/inject", "POST") is True
    assert _is_public("/api/v1/consultation/task-1/inject", "POST") is True


@pytest.mark.parametrize("path", [
    "/api/v1/collaboration/task-1/session",
    "/api/v1/consultation/task-1/session",
    "/api/v1/collaboration/task-1/sessions/s-1/approve",
    "/api/v1/consultation/task-1/sessions/s-1/approve",
    "/api/v1/collaboration/task-1/sessions/s-1/end_consultation",
    "/api/v1/collaboration/task-1/invite",
])
def test_owner_only_endpoints_remain_protected(path):
    assert _is_public(path, "GET") is False
    assert _is_public(path, "POST") is False
