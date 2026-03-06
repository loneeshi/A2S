---
description: Auto-generated skill for pick_and_place tasks based on 3 failure reflections
whenToUse: >-
  When handling pick_and_place tasks, especially to avoid:
  timeout:iteration_limit
steps:
  - 分析任务目标，确认需要的工具和操作序列
  - 观察环境状态，定位目标物体
  - 执行操作并验证每步结果
  - 确认任务完成
tags:
  - manipulation
  - pick_and_place
  - auto-generated
---
## 避免超时失败的技能指南

在操作“pick_and_place”任务时，代理可能会遇到超时失败。以下是避免这些失败的步骤和策略。

## 工作流程

1. **任务规划**
   - 在开始之前，仔细分析任务的复杂性。
   - 确定所需的工具和步骤，例如使用 `env.goto` 定位目标位置，使用 `env.take` 拿起物体。

2. **优化执行策略**
   - 将任务分解为更小的子任务，逐步完成。
   - 确保每一步都在合理的时间内完成，避免不必要的延迟。

3. **设置合理的迭代限制**
   - 根据任务的复杂性设置最大迭代次数，确保它足够大以完成任务。
   - 如果任务需要更多时间，考虑增加最大迭代次数。

4. **实时监控**
   - 在执行过程中，监控任务进展，及时调整策略。
   - 如果发现某个步骤耗时过长，立即评估并优化。

## 常见错误

- **未考虑任务复杂性**
  - 预先评估任务的难度，确保迭代次数足够。
  
- **缺乏有效的分步计划**
  - 不要一次性尝试完成整个任务，分步执行可以降低超时风险。

- **忽视工具使用**
  - 确保正确使用 `env.goto`、`env.take` 等工具，避免因操作不当导致的延误。

## 恢复策略

当遇到超时失败时，可以采取以下措施：

1. **分析失败原因**
   - 回顾任务执行过程，确定是哪个步骤导致了超时。

2. **调整策略**
   - 如果某个步骤过于复杂，考虑简化或重新规划。

3. **增加迭代次数**
   - 如果任务确实需要更多时间，适当增加最大迭代次数。

4. **重试任务**
   - 在做出必要调整后，重新开始任务，确保遵循优化后的执行策略。

通过遵循这些步骤和策略，代理可以有效减少在“pick_and_place”任务中的超时失败，提升操作效率。

### 新增失败模式 (2026-03-06)
- The task exceeded the maximum allowed iterations without completion, indicating potential inefficiencies in the task execution or planning.
- The task did not complete within the maximum allowed iterations, indicating a potential issue with the task complexity or agent performance.
- The task could not be completed within the maximum allowed iterations, indicating potential inefficiencies in the task execution process.
