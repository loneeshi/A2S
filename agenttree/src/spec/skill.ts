/**
 * SkillSpec v2 — aligned with Claude Code's skill framework + A2S research extensions.
 *
 * Claude Code concepts mapped:
 *   name → id (path-based: "alfworld/task_decomposition")
 *   description → description
 *   disable-model-invocation + user-invocable → invocation
 *   allowed-tools → allowedTools
 *   context → context (inline | fork)
 *   agent → agent
 *   model → model
 *   hooks → hooks
 *
 * A2S-specific extensions:
 *   whenToUse, steps, tags — original fields
 *   type — content classification (reference | task | workflow)
 *   arguments — structured argument schema
 *   generatedBy — auto-generation tracking
 *   probation — extension engine validation
 */

import { z } from "zod"

export const SkillInvocationSchema = z.object({
  modelCanInvoke: z.boolean().default(true),
  userCanInvoke: z.boolean().default(true),
})

export type SkillInvocation = z.infer<typeof SkillInvocationSchema>

export const SkillArgumentSchema = z.object({
  name: z.string(),
  description: z.string(),
  required: z.boolean().default(false),
})

export type SkillArgument = z.infer<typeof SkillArgumentSchema>

export const SkillHookSchema = z.object({
  event: z.enum(["preInvoke", "postInvoke", "onError"]),
  command: z.string(),
})

export type SkillHook = z.infer<typeof SkillHookSchema>

export const SkillProbationSchema = z.object({
  status: z.enum(["active", "probation", "disabled"]).default("probation"),
  tasksHandled: z.number().default(0),
  successRate: z.number().default(0),
  baselineRate: z.number().default(0),
})

export type SkillProbation = z.infer<typeof SkillProbationSchema>

export const SkillSpecSchema = z.object({
  id: z.string().min(1),
  description: z.string().min(1),

  type: z.enum(["reference", "task", "workflow"]).default("reference"),

  whenToUse: z.string().default(""),
  steps: z.array(z.string()).default([]),
  tags: z.array(z.string()).default([]),
  version: z.string().optional(),

  invocation: SkillInvocationSchema.default({ modelCanInvoke: true, userCanInvoke: true }),

  allowedTools: z.array(z.string()).optional(),

  arguments: z.array(SkillArgumentSchema).optional(),

  context: z.enum(["inline", "fork"]).default("inline"),
  agent: z.string().optional(),
  model: z.string().optional(),

  hooks: z.array(SkillHookSchema).optional(),

  generatedBy: z.enum(["manual", "evolution", "extension"]).optional(),
  probation: SkillProbationSchema.optional(),
})

export type SkillSpec = z.infer<typeof SkillSpecSchema>

export type SkillSpecInput = z.input<typeof SkillSpecSchema>
