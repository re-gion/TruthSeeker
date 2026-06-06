# LangGraph Agent Guide

## Scope

This file applies to `truthseeker-api/app/agents/`.

## Core Rules

- LangGraph state must be defined with `TypedDict`; do not use Pydantic `BaseModel` for graph state.
- Keep the canonical state shape in `state.py`. Update it first when adding state fields.
- Agent nodes should return partial state updates that match existing reducer expectations.
- Preserve the four-agent flow: Forensics, OSINT, Challenger, Commander.
- The current graph is staged: `START -> forensics -> challenger -> osint -> challenger -> commander -> END`.
- Commander now ends directly after final verdict generation. Do not reintroduce `commander -> challenger` unless the product flow and docs are changed together.
- Keep convergence and routing logic in `edges/conditions.py`, not scattered inside nodes.
- External service wrappers belong in `tools/`; node files should orchestrate tool results and reasoning.
- Any network/API tool must degrade safely and return structured fallback data instead of crashing the graph.
- Logs and timeline events should be safe for SSE/UI display and must not include secrets, raw tokens, or full third-party payloads.
- Before round 5, Challenger confidence `< 0.8` must return the target Agent for additional evidence. At round 5, release with `max_rounds_release=true` and residual risk.
- Collaboration trigger logic is target-agent scoped; do not count low-confidence rounds from a different phase.

## Testing

When changing agent state, nodes, edges, or tools, add or update pytest coverage under `truthseeker-api/tests/`. Prefer deterministic fake tool responses and assert final state, evidence, logs, and termination reason.
