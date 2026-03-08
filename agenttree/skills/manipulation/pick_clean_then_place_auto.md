---
description: >-
  Auto-generated skill for pick_clean_then_place tasks based on 3 failure
  reflections
whenToUse: >-
  When handling pick_clean_then_place tasks, especially to avoid:
  timeout:iteration_limit
steps:
  - 分析任务目标，确认需要的工具和操作序列
  - 观察环境状态，定位目标物体
  - 执行操作并验证每步结果
  - 确认任务完成
tags:
  - manipulation
  - pick_clean_then_place
  - auto-generated
---
## 避免超时失败的技能指南

在执行“pick_clean_then_place”任务时，超时失败是一个常见问题。以下是避免这些失败的步骤和策略。

## 工作流程

1. **任务规划**
   - 评估当前环境和物体位置。
   - 使用 `env.goto` 确定最佳路径到目标物体。

2. **执行清理**
   - 使用 `env.take` 拾取目标物体。
   - 确保在拾取过程中没有障碍物影响。

3. **放置物体**
   - 使用 `env.goto` 移动到放置位置。
   - 使用 `env.place` 将物体放置在指定位置。

4. **监控进度**
   - 在每个步骤之间检查是否在允许的迭代次数内完成。
   - 如果接近超时，考虑调整策略。

## 常见错误

- **忽视环境评估**  
  确保在开始任务前评估环境，避免因障碍物导致的迭代失败。

- **不合理的路径选择**  
  使用 `env.goto` 时，选择最短且最有效的路径，避免不必要的迭代。

- **未能及时调整策略**  
  如果发现任务进展缓慢，应立即调整策略，而不是等待超时。

## 恢复策略

如果任务失败并出现超时，请遵循以下恢复策略：

1. **分析失败原因**
   - 回顾任务执行日志，找出造成超时的具体步骤。

2. **调整迭代限制**
   - 根据任务复杂性，适当增加最大迭代次数。

3. **优化执行策略**
   - 针对识别出的瓶颈，调整使用的工具和方法。例如，尝试不同的路径或清理方式。

4. **重新执行任务**
   - 在优化后，重新开始任务，确保监控每一步的进展。

通过遵循这些步骤和策略，您将能够有效地避免在“pick_clean_then_place”任务中遇到的超时失败。

### 新增失败模式 (2026-03-06)
- The task exceeded the maximum allowed iterations without completion, indicating potential inefficiencies in the task execution or planning.
- The task did not complete within the allowed iterations, indicating a potential inefficiency in the process or an overly complex task.
