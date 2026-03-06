import { z } from "zod"

export const SkillSpecSchema = z.object({
  id: z.string().min(1),
  description: z.string().min(1),
  whenToUse: z.string().min(1),
  steps: z.array(z.string()).default([]),
  tags: z.array(z.string()).default([]),
  version: z.string().optional(),
})

export type SkillSpec = z.infer<typeof SkillSpecSchema>
