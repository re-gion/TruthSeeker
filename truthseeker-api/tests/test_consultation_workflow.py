from app.services.consultation_workflow import (
    build_moderator_summary,
    evaluate_consultation_trigger,
)


def _challenge(
    *,
    target_agent="forensics",
    confidence=0.72,
    high=True,
    quality_delta=0.02,
    round_number=1,
):
    return {
        "round": round_number,
        "target_agent": target_agent,
        "phase": target_agent,
        "confidence": confidence,
        "quality_delta": quality_delta,
        "high_severity_count": 1 if high else 0,
        "issues": [
            {"severity": "high" if high else "medium", "description": "证据链无法闭合"}
        ],
    }


def test_three_round_low_confidence_stable_high_challenge_triggers_consultation():
    result = evaluate_consultation_trigger(
        [
            _challenge(confidence=0.74, quality_delta=None, round_number=1),
            _challenge(confidence=0.71, quality_delta=0.03, round_number=2),
            _challenge(confidence=0.69, quality_delta=0.02, round_number=3),
        ],
        existing_sessions=[],
    )

    assert result["should_pause"] is True
    assert result["event_type"] == "consultation_required"
    assert result["target_agent"] == "forensics"
    assert result["repeat_index"] == 1


def test_three_round_trigger_requires_same_target_and_adjacent_delta():
    mixed_target = evaluate_consultation_trigger(
        [
            _challenge(target_agent="forensics", round_number=1),
            _challenge(target_agent="osint", round_number=2),
            _challenge(target_agent="forensics", round_number=3),
        ],
        existing_sessions=[],
    )
    noisy_delta = evaluate_consultation_trigger(
        [
            _challenge(confidence=0.62, quality_delta=None, round_number=1),
            _challenge(confidence=0.77, quality_delta=0.15, round_number=2),
            _challenge(confidence=0.70, quality_delta=0.07, round_number=3),
        ],
        existing_sessions=[],
    )

    assert mixed_target["should_pause"] is False
    assert noisy_delta["should_pause"] is False


def test_repeated_deadlock_requires_user_approval_before_consultation():
    result = evaluate_consultation_trigger(
        [
            _challenge(confidence=0.74, quality_delta=None, round_number=1),
            _challenge(confidence=0.71, quality_delta=0.03, round_number=2),
            _challenge(confidence=0.69, quality_delta=0.02, round_number=3),
        ],
        existing_sessions=[{"id": "session-1", "status": "summary_confirmed"}],
    )

    assert result["should_pause"] is True
    assert result["event_type"] == "consultation_approval_required"
    assert result["requires_user_approval"] is True
    assert result["repeat_index"] == 2


def test_moderator_summary_uses_confirmed_user_text_when_present():
    summary = build_moderator_summary(
        messages=[
            {"role": "expert", "message": "建议核验原始发布时间"},
            {"role": "user", "message": "我认为需要优先查证来源账号"},
        ],
        user_confirmed_summary="用户确认：来源账号是破局关键。",
    )

    assert summary["confirmed_summary"] == "用户确认：来源账号是破局关键。"
    assert summary["message_count"] == 2
    assert summary["key_quotes"][0]["role"] == "expert"
