import publicBindings from "./agent-skills.json"

export type AgentSkillBinding = {
  name: string
  label: string
  version: string
}

export const AGENT_SKILL_BINDINGS: Record<string, AgentSkillBinding> = publicBindings

export function getAgentSkillBinding(agentKey: string) {
  return AGENT_SKILL_BINDINGS[agentKey]
}
