import matter from "gray-matter"
import { AgentSpecSchema, type AgentSpec } from "../spec/agent"

export interface ParsedAgent {
  spec: AgentSpec
  prompt: string
  raw: string
}

export function parseAgentFile(raw: string): ParsedAgent {
  const { data, content } = matter(raw)
  const spec = AgentSpecSchema.parse(data)
  return { spec, prompt: content.trim(), raw }
}

export function stringifyAgentFile(spec: AgentSpec, prompt: string): string {
  const { id, name, role, mode, description, tools, memory, skills, metadata } = spec

  const frontmatter: Record<string, unknown> = {
    id,
    name,
    role,
    mode,
  }

  if (description) frontmatter.description = description

  if (tools.allow.length > 0 || tools.deny.length > 0) {
    frontmatter.tools = tools
  }

  if (memory.mode !== "light" || memory.store !== "jsonl" || memory.capacity !== 200 || memory.ttlHours !== undefined) {
    frontmatter.memory = memory
  }

  if (skills.length > 0) frontmatter.skills = skills

  if (Object.keys(metadata).length > 0) frontmatter.metadata = metadata

  return matter.stringify(prompt, frontmatter)
}
