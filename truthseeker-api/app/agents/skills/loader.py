"""Strict loader for Agent-bound Markdown Skill packages.

The loader reads declarative Markdown only. It never executes package code,
installs tools, or changes deterministic routing and scoring rules.
"""

from __future__ import annotations

import hashlib
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SKILLS_ROOT = Path(__file__).resolve().parent / "packages"
SUPPORTED_SCHEMA_VERSION = 1
ALLOWED_FRONTMATTER_FIELDS = {
    "name",
    "description",
    "version",
    "schema_version",
    "agent",
    "workflows",
}
REQUIRED_BODY_SECTIONS = (
    "## 适用场景",
    "## 输入边界",
    "## 标准步骤",
    "## 允许工具",
    "## 证据门槛",
    "## 禁止事项",
    "## 输出要求",
    "## 自检清单",
    "## 降级策略",
)
SEMVER_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


@dataclass(frozen=True)
class SkillBinding:
    agent: str
    skill_name: str
    workflows: tuple[str, ...]
    contract_checks: tuple[str, ...] = ()
    required_output_headings: tuple[str, ...] = ()


@dataclass(frozen=True)
class SkillLoadResult:
    prompt_context: str
    execution: dict[str, Any]


AGENT_SKILL_BINDINGS: dict[str, SkillBinding] = {
    "forensics": SkillBinding(
        agent="forensics",
        skill_name="multimodal-forensics",
        workflows=("primary_analysis",),
        contract_checks=("required_report_sections",),
        required_output_headings=(
            "### 自主检材观察",
            "### 外部检测结果解读",
            "### 融合判断",
            "### 限制与复核建议",
        ),
    ),
    "osint": SkillBinding(
        agent="osint",
        skill_name="osint-provenance",
        workflows=("primary_analysis",),
        contract_checks=("provenance_boundaries",),
    ),
    "challenger": SkillBinding(
        agent="challenger",
        skill_name="evidence-challenge",
        workflows=("phase_review",),
        contract_checks=("phase_scope",),
    ),
    "commander": SkillBinding(
        agent="commander",
        skill_name="command-collaboration",
        workflows=("final_adjudication", "human_collaboration", "experience_distillation"),
        contract_checks=("workflow_output_contract",),
    ),
}

WORKFLOW_CONTRACTS: dict[tuple[str, str], dict[str, Any]] = {
    ("forensics", "primary_analysis"): {
        "checks": ("required_report_sections",),
        "headings": AGENT_SKILL_BINDINGS["forensics"].required_output_headings,
    },
    ("osint", "primary_analysis"): {
        "checks": ("required_report_sections",),
        "headings": (
            "### 自主情报推理",
            "### 外部情报结果解读",
            "### 来源可信度与图谱质量",
            "### 关联风险与复核建议",
        ),
    },
    ("challenger", "phase_review"): {
        "checks": ("required_report_sections",),
        "headings": (
            "### 质询对象与本轮置信度",
            "### 主要质询点",
            "### 打回/放行建议",
            "### 收敛依据",
        ),
    },
    ("commander", "final_adjudication"): {
        "checks": ("required_report_sections", "commander_verdict_category"),
        "headings": (
            "### 最终裁决结论",
            "### 置信度与证据链",
            "### Agent 结论与关键分歧",
            "### 后续建议与风险",
        ),
    },
    ("commander", "human_collaboration"): {
        "checks": ("human_collaboration_contract",),
    },
    ("commander", "experience_distillation"): {
        "checks": ("experience_distillation_contract",),
    },
}


class SkillContractError(ValueError):
    """Raised internally when a declarative Skill contract is invalid."""


def load_agent_skill(
    agent: str,
    workflow: str,
    *,
    skills_root: Path | None = None,
) -> SkillLoadResult:
    """Load one fixed Agent Skill without ever failing the analysis pipeline."""
    binding = AGENT_SKILL_BINDINGS.get(agent)
    if binding is None:
        return _unavailable_result(
            skill_name=None,
            workflow=workflow,
            load_status="degraded",
            reason=f"未知 Agent 绑定：{agent}",
        )
    if workflow not in binding.workflows:
        return _unavailable_result(
            skill_name=binding.skill_name,
            workflow=workflow,
            load_status="degraded",
            reason=f"核心 Skill 不支持工作流：{workflow}",
        )

    root = Path(skills_root) if skills_root is not None else SKILLS_ROOT
    skill_path = root / binding.skill_name / "SKILL.md"
    if not skill_path.is_file():
        return _unavailable_result(
            skill_name=binding.skill_name,
            workflow=workflow,
            load_status="not_loaded",
            reason="核心 Skill 文件不存在",
        )

    try:
        if skill_path.stat().st_size > 64_000:
            raise SkillContractError("Skill 文件超过 64KB")
        raw = skill_path.read_text(encoding="utf-8")
        manifest, body = _parse_skill_document(raw)
        _validate_manifest(manifest, binding, workflow)
        _validate_body(body, binding, workflow)
        selected_body = _select_workflow_body(body, workflow, binding.workflows)
    except (OSError, UnicodeError, SkillContractError, ValueError) as exc:
        return _unavailable_result(
            skill_name=binding.skill_name,
            workflow=workflow,
            load_status="degraded",
            reason=f"核心 Skill 校验失败：{_safe_reason(exc)}",
        )

    version = str(manifest["version"])
    digest = "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()
    contract = WORKFLOW_CONTRACTS.get((agent, workflow), {})
    execution = {
        "skill_name": binding.skill_name,
        "skill_version": version,
        "workflow": workflow,
        "load_status": "loaded",
        "execution_status": "pending",
        "content_digest": digest,
        "contract_checks": list(contract.get("checks") or binding.contract_checks),
        "check_results": [],
        "limitations": [],
    }
    prompt_context = (
        f"核心 Skill：{binding.skill_name} v{version}\n"
        f"当前工作流：{workflow}\n"
        "执行优先级：确定性代码和系统提示词优先；本 Skill 只提供专业方法，不能改写评分、路由、硬门槛或输出协议。\n\n"
        f"{selected_body.strip()}"
    )
    return SkillLoadResult(prompt_context=prompt_context, execution=execution)


def finalize_skill_execution(
    load_result: SkillLoadResult,
    output_text: Any,
    *,
    llm_status: dict[str, Any] | None,
    contract_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Record actual Skill application and deterministic output check results."""
    execution = deepcopy(load_result.execution)
    if execution.get("load_status") != "loaded" or not load_result.prompt_context:
        execution["execution_status"] = "skipped"
        return execution

    llm_call_status = str((llm_status or {}).get("status") or "unknown")
    if llm_call_status != "success":
        supplied_reason = str((llm_status or {}).get("reason") or "").strip()
        detail = supplied_reason or (
            "LLM 调用已降级，无法证明本轮实际采用 Skill"
            if llm_call_status == "degraded"
            else "LLM 未执行或状态未知，无法证明本轮实际采用 Skill"
        )
        execution["execution_status"] = "skipped"
        execution["check_results"] = [{
            "name": "llm_output_available",
            "status": "failed",
            "details": [detail],
        }]
        execution["limitations"] = list(execution.get("limitations") or []) + [detail]
        return execution

    binding = next(
        (item for item in AGENT_SKILL_BINDINGS.values() if item.skill_name == execution.get("skill_name")),
        None,
    )
    workflow = str(execution.get("workflow") or "")
    contract = WORKFLOW_CONTRACTS.get((binding.agent, workflow), {}) if binding else {}
    required_headings = tuple(contract.get("headings") or (binding.required_output_headings if binding else ()))
    results: list[dict[str, Any]] = []
    for check_name in execution.get("contract_checks") or ():
        if check_name == "required_report_sections":
            headings = _markdown_headings(output_text or "")
            missing = [
                heading
                for heading in required_headings
                if headings.count(heading) == 0
            ]
            duplicates = [
                heading
                for heading in required_headings
                if headings.count(heading) > 1
            ]
            present = [heading for heading in required_headings if heading in headings]
            wrong_order = present != sorted(present, key=headings.index)
            empty = [
                heading
                for heading in required_headings
                if headings.count(heading) == 1
                and not _markdown_section_body(output_text or "", heading)
            ]
            details = [f"缺少章节：{heading}" for heading in missing]
            details.extend(f"章节重复：{heading}" for heading in duplicates)
            if wrong_order:
                details.append("章节顺序错误")
            details.extend(f"章节正文为空：{heading}" for heading in empty)
            results.append({
                "name": check_name,
                "status": "failed" if details else "passed",
                "details": details,
            })
        elif check_name == "commander_verdict_category":
            verdict_body = _markdown_section_body(str(output_text or ""), "### 最终裁决结论")
            allowed = ("伪造", "可疑", "真实", "无法判定")
            matched = [item for item in allowed if item in verdict_body]
            details = [] if len(matched) == 1 else ["最终裁决结论必须且只能包含一个四分类结果"]
            expected = str((contract_context or {}).get("expected_verdict_cn") or "").strip()
            if len(matched) == 1 and expected and matched[0] != expected:
                details.append(f"LLM 裁决 {matched[0]} 与确定性裁决 {expected} 不一致")
            results.append({
                "name": check_name,
                "status": "failed" if details else "passed",
                "details": details,
            })
        elif check_name == "human_collaboration_contract":
            details = _human_collaboration_contract_details(output_text)
            results.append({
                "name": check_name,
                "status": "failed" if details else "passed",
                "details": details,
            })
        elif check_name == "experience_distillation_contract":
            details = _experience_distillation_contract_details(output_text)
            results.append({
                "name": check_name,
                "status": "failed" if details else "passed",
                "details": details,
            })
        else:
            results.append({
                "name": check_name,
                "status": "not_implemented",
                "details": ["代码侧检查器尚未实现"],
            })

    execution["check_results"] = results
    failed = [item for item in results if item.get("status") != "passed"]
    if failed:
        execution["execution_status"] = "check_failed"
        execution["limitations"] = list(execution.get("limitations") or []) + [
            "Skill 输出检查未通过：" + "、".join(str(item.get("name")) for item in failed)
        ]
    else:
        execution["execution_status"] = "applied"
    return execution


def _human_collaboration_contract_details(output: Any) -> list[str]:
    if not isinstance(output, dict):
        return ["协同输出必须为对象"]
    if "help_needed" in output or "expert_tasks" in output:
        required_lists = ("help_needed", "expert_tasks")
        details = [f"{field} 必须为数组" for field in required_lists if not isinstance(output.get(field), list)]
        help_needed = output.get("help_needed")
        if isinstance(help_needed, list) and any(not isinstance(item, str) or not item.strip() for item in help_needed):
            details.append("help_needed 每项必须为非空字符串")
        required_task_fields = {
            "target_agent": str,
            "issue_type": str,
            "severity": str,
            "question": str,
            "requested_action": str,
            "expected_output": str,
        }
        for index, task in enumerate(output.get("expert_tasks") or []):
            if not isinstance(task, dict):
                details.append(f"expert_tasks[{index}] 必须为对象")
                continue
            for field, expected_type in required_task_fields.items():
                value = task.get(field)
                if not isinstance(value, expected_type) or not value.strip():
                    details.append(f"expert_tasks[{index}].{field} 类型无效或为空")
        return details
    required = {
        "generated_summary": str,
        "expert_answer_summary": str,
        "recommended_actions": list,
        "unresolved_questions": list,
    }
    details = [
        f"{field} 类型无效或缺失"
        for field, expected_type in required.items()
        if not isinstance(output.get(field), expected_type)
    ]
    if isinstance(output.get("generated_summary"), str) and not output["generated_summary"].strip():
        details.append("generated_summary 不能为空")
    for field in ("recommended_actions", "unresolved_questions"):
        value = output.get(field)
        if isinstance(value, list) and any(not isinstance(item, str) for item in value):
            details.append(f"{field} 每项必须为字符串")
    return details


def _experience_distillation_contract_details(output: Any) -> list[str]:
    if not isinstance(output, dict) or not isinstance(output.get("drafts"), list):
        return ["drafts 必须为数组"]
    details: list[str] = []
    required_fields = {
        "title": str,
        "target_agents": list,
        "problem_pattern": str,
        "recommended_method": str,
        "evidence_to_check": list,
        "when_to_escalate": str,
        "limitations": str,
    }
    allowed_agents = {"forensics", "osint", "challenger"}
    for index, draft in enumerate(output["drafts"]):
        if not isinstance(draft, dict):
            details.append(f"drafts[{index}] 必须为对象")
            continue
        for field, expected_type in required_fields.items():
            value = draft.get(field)
            if not isinstance(value, expected_type):
                details.append(f"drafts[{index}].{field} 类型无效或缺失")
        for field in ("title", "problem_pattern", "recommended_method"):
            if isinstance(draft.get(field), str) and not draft[field].strip():
                details.append(f"drafts[{index}].{field} 不能为空")
        targets = draft.get("target_agents")
        if isinstance(targets, list) and (
            not targets or any(not isinstance(item, str) or item not in allowed_agents for item in targets)
        ):
            details.append(f"drafts[{index}].target_agents 包含无效 Agent")
        evidence = draft.get("evidence_to_check")
        if isinstance(evidence, list) and any(not isinstance(item, str) for item in evidence):
            details.append(f"drafts[{index}].evidence_to_check 每项必须为字符串")
    return details


def _unavailable_result(
    *,
    skill_name: str | None,
    workflow: str,
    load_status: str,
    reason: str,
) -> SkillLoadResult:
    return SkillLoadResult(
        prompt_context="",
        execution={
            "skill_name": skill_name,
            "skill_version": None,
            "workflow": workflow,
            "load_status": load_status,
            "execution_status": "skipped",
            "content_digest": None,
            "contract_checks": [],
            "check_results": [],
            "limitations": [reason],
        },
    )


def _parse_skill_document(raw: str) -> tuple[dict[str, Any], str]:
    normalized = raw.replace("\r\n", "\n")
    match = re.match(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", normalized, flags=re.DOTALL)
    if not match:
        raise SkillContractError("缺少完整 YAML frontmatter")

    manifest: dict[str, Any] = {}
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            raise SkillContractError("frontmatter 行格式错误")
        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        if key not in ALLOWED_FRONTMATTER_FIELDS:
            raise SkillContractError(f"frontmatter 包含未允许字段：{key}")
        if key in manifest:
            raise SkillContractError(f"frontmatter 字段重复：{key}")
        manifest[key] = _parse_frontmatter_value(key, raw_value.strip())
    return manifest, match.group(2).strip()


def _parse_frontmatter_value(key: str, value: str) -> Any:
    if key == "schema_version":
        try:
            return int(value)
        except ValueError as exc:
            raise SkillContractError("schema_version 必须为整数") from exc
    if key == "workflows":
        if not (value.startswith("[") and value.endswith("]")):
            raise SkillContractError("workflows 必须使用行内列表")
        items = [item.strip().strip("\"'") for item in value[1:-1].split(",") if item.strip()]
        if not items:
            raise SkillContractError("workflows 不能为空")
        return items
    return value.strip("\"'")


def _validate_manifest(manifest: dict[str, Any], binding: SkillBinding, workflow: str) -> None:
    required = {"name", "description", "version", "schema_version", "agent", "workflows"}
    missing = sorted(required - manifest.keys())
    if missing:
        raise SkillContractError("frontmatter 缺少字段：" + ", ".join(missing))
    if manifest["name"] != binding.skill_name:
        raise SkillContractError("Skill 名称与固定绑定不一致")
    if manifest["agent"] != binding.agent:
        raise SkillContractError("Agent 与固定绑定不一致")
    if manifest["schema_version"] != SUPPORTED_SCHEMA_VERSION:
        raise SkillContractError("schema_version 不受支持")
    if not SEMVER_PATTERN.fullmatch(str(manifest["version"])):
        raise SkillContractError("version 必须为三段语义版本")
    if not str(manifest["description"]).strip():
        raise SkillContractError("description 不能为空")
    if tuple(manifest["workflows"]) != binding.workflows:
        raise SkillContractError("workflows 与固定绑定不一致")
    if workflow not in manifest["workflows"]:
        raise SkillContractError("请求工作流未在 Skill 中声明")


def _validate_body(body: str, binding: SkillBinding, workflow: str) -> None:
    if not body or len(body) > 64_000:
        raise SkillContractError("Skill 正文为空或超过 64KB")
    headings = _markdown_headings(body)
    heading_counts = {heading: headings.count(heading) for heading in set(headings)}
    missing_sections = [section for section in REQUIRED_BODY_SECTIONS if heading_counts.get(section, 0) == 0]
    if missing_sections:
        raise SkillContractError("Skill 正文缺少章节：" + ", ".join(missing_sections))
    duplicate_sections = [section for section in REQUIRED_BODY_SECTIONS if heading_counts.get(section, 0) > 1]
    if duplicate_sections:
        raise SkillContractError("Skill 正文章节重复：" + ", ".join(duplicate_sections))
    section_positions = [headings.index(section) for section in REQUIRED_BODY_SECTIONS]
    if section_positions != sorted(section_positions):
        raise SkillContractError("Skill 正文章节顺序错误")
    empty_sections = [
        section for section in REQUIRED_BODY_SECTIONS if not _markdown_section_body(body, section)
    ]
    if empty_sections:
        raise SkillContractError("Skill 正文章节正文为空：" + ", ".join(empty_sections))
    if len(binding.workflows) > 1:
        if heading_counts.get("## 工作流", 0) != 1:
            raise SkillContractError("多工作流 Skill 缺少工作流章节")
        for declared_workflow in binding.workflows:
            workflow_heading = f"### {declared_workflow}"
            if heading_counts.get(workflow_heading, 0) != 1:
                raise SkillContractError(f"缺少工作流正文：{declared_workflow}")
            if not _workflow_body(body, declared_workflow):
                raise SkillContractError(f"工作流正文为空：{declared_workflow}")
        if heading_counts.get(f"### {workflow}", 0) != 1:
            raise SkillContractError(f"缺少当前工作流正文：{workflow}")


def _select_workflow_body(body: str, workflow: str, workflows: tuple[str, ...]) -> str:
    if len(workflows) == 1:
        return body

    before: list[str] = []
    selected: list[str] = []
    after: list[str] = []
    in_workflow_section = False
    selected_active = False
    workflow_section_ended = False
    fence_char: str | None = None
    fence_length = 0

    def append_content(line: str) -> None:
        if in_workflow_section:
            if selected_active:
                selected.append(line)
        elif workflow_section_ended:
            after.append(line)
        else:
            before.append(line)

    for line in body.splitlines():
        fence_match = re.match(r"^[ \t]{0,3}(`{3,}|~{3,})", line)
        if fence_match:
            append_content(line)
            marker = fence_match.group(1)
            if fence_char is None:
                fence_char = marker[0]
                fence_length = len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_length:
                fence_char = None
                fence_length = 0
            continue
        if fence_char is not None:
            append_content(line)
            continue
        if line.strip() == "## 工作流":
            in_workflow_section = True
            before.append("## 当前工作流")
            before.append(f"### {workflow}")
            continue
        if in_workflow_section and line.startswith("## "):
            in_workflow_section = False
            workflow_section_ended = True
            selected_active = False
            after.append(line)
            continue
        if in_workflow_section and line.startswith("### "):
            selected_active = line.strip() == f"### {workflow}"
            continue
        append_content(line)

    return "\n".join(before + selected + after).strip()


def _safe_reason(exc: Exception) -> str:
    reason = " ".join(str(exc).split())
    return reason[:240] or type(exc).__name__


def _markdown_headings(body: str) -> list[str]:
    headings: list[str] = []
    for line in _markdown_lines_outside_fences(body):
        match = re.match(r"^(#{2,3})[ \t]+(.+?)[ \t]*$", line)
        if match:
            headings.append(f"{match.group(1)} {match.group(2).strip()}")
    return headings


def _markdown_lines_outside_fences(body: str):
    fence_char: str | None = None
    fence_length = 0
    for line in body.splitlines():
        fence_match = re.match(r"^[ \t]{0,3}(`{3,}|~{3,})", line)
        if fence_match:
            marker = fence_match.group(1)
            if fence_char is None:
                fence_char = marker[0]
                fence_length = len(marker)
            elif marker[0] == fence_char and len(marker) >= fence_length:
                fence_char = None
                fence_length = 0
            continue
        if fence_char is None:
            yield line


def _markdown_section_body(body: str, heading: str) -> str:
    target_level = len(heading) - len(heading.lstrip("#"))
    active = False
    content: list[str] = []
    for line in _markdown_lines_outside_fences(body):
        match = re.match(r"^(#{1,6})[ \t]+(.+?)[ \t]*$", line)
        normalized = f"{match.group(1)} {match.group(2).strip()}" if match else None
        if not active:
            if normalized == heading:
                active = True
            continue
        if match and len(match.group(1)) <= target_level:
            break
        content.append(line)
    return "\n".join(content).strip()


def _workflow_body(body: str, workflow: str) -> str:
    return _markdown_section_body(body, f"### {workflow}")
