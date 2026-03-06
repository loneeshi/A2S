---
description: Efficiency strategies to avoid timeout failures
whenToUse: When tasks frequently time out or take too many steps
steps:
  - 优先搜索最可能的位置
  - 避免重复访问已检查的位置
  - 跟踪已访问位置的列表
  - 使用环境线索缩小搜索范围
tags:
  - common
  - efficiency
  - auto-generated
---
## 效率优化（自动生成）

### 搜索策略
1. 先 `env.look` 观察当前位置，获取可见物体和位置列表
2. 根据任务类型优先搜索最可能的位置（如找食物先检查 fridge、countertop）
3. 记住已检查过的位置，不要重复访问
4. 如果前 5 个位置都没找到目标，重新审视任务描述

### 操作效率
- 先导航到目标位置再操作（减少 'Nothing happens' 错误）
- 一次行动完成一个子目标
- 不要在已完成的步骤上重复操作
