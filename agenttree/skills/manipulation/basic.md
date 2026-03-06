---
id: manipulation/basic
description: 基础物体操作技能
whenToUse: 需要拿取、放置、清洁、加热或冷却物体时
steps:
  - 确认目标物体和目标位置
  - 导航到物体位置
  - 拿取物体（如容器关闭需先打开）
  - 执行必要操作（clean/heat/cool）
  - 导航到目标位置并放置
  - 验证结果
tags:
  - manipulation
  - object-interaction
version: 0.1.0
---

## Pick and Place 操作模式

### 基本流程
1. `look` 确认环境状态
2. `goto` 导航到物体位置
3. 如果物体在封闭容器中，先 `open` 容器
4. `take` 拿取物体
5. 如果需要清洁：`goto sinkbasin` → `clean object sinkbasin`
6. 如果需要加热：`goto microwave` → `heat object microwave`
7. 如果需要冷却：`goto fridge` → `cool object fridge`
8. `goto` 导航到目标位置
9. `put` 放置物体

### 关键注意事项
- 一次只能持有一个物体
- 操作前确认物体名称完全正确（包括编号如 "apple 1"）
- 放置前确认目标容器可以接收该物体
- 清洁必须在 sinkbasin 进行，加热必须在 microwave，冷却必须在 fridge
