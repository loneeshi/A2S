import { z } from "zod"

export const ToolPolicySchema = z.object({
  allow: z.array(z.string()).default([]),
  deny: z.array(z.string()).default([]),
})

export type ToolPolicy = z.infer<typeof ToolPolicySchema>

export const MemoryConfigSchema = z.object({
  mode: z.enum(["light", "full", "off"]).default("light"),
  store: z.enum(["jsonl", "sqlite"]).default("jsonl"),
  ttlHours: z.number().positive().optional(),
  capacity: z.number().int().positive().default(200),
})

export type MemoryConfig = z.infer<typeof MemoryConfigSchema>

export const AgentSpecSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  role: z.enum(["worker", "manager", "orchestrator"]),
  mode: z.enum(["all", "primary", "subagent"]).default("all"),
  description: z.string().optional(),
  tools: ToolPolicySchema.default({ allow: [], deny: [] }),
  memory: MemoryConfigSchema.default({ mode: "light", store: "jsonl", capacity: 200 }),
  skills: z.array(z.string()).default([]),
  metadata: z.record(z.string(), z.any()).default({}),
})

export type AgentSpec = z.infer<typeof AgentSpecSchema>
