---
id: perception/basic
description: 基础环境感知技能
whenToUse: 需要搜索物体、观察环境或确认物体状态时
steps:
  - 在当前位置使用 look 观察
  - 逐一检查可见的容器和表面
  - 记录发现的物体和位置
  - 导航到其他位置继续搜索
  - 汇总观察结果
tags:
  - perception
  - search
  - observation
version: 0.1.0
---

## 环境搜索策略

### 系统性搜索
1. `look` 观察当前房间概况
2. 对每个可见的 receptacle：
   - 如果是封闭容器（fridge, cabinet, drawer），先 `open`
   - 使用 `examine` 检查内容
3. 记录所有发现的物体（名称 + 编号 + 位置）
4. 使用 `goto` 移动到下一个区域
5. 重复搜索直到覆盖所有区域

### 常见 receptacle 列表
- countertop, shelf, drawer, cabinet
- fridge, microwave, stoveburner
- sinkbasin, bathtub, toilet
- desk, dresser, sidetable, coffeetable
- bed, sofa, armchair
- garbagecan, safe

### 注意事项
- 不要假设物体位置，必须亲自搜索
- 打开容器后注意记录内容
- 同一种物体可能有多个（apple 1, apple 2），需要区分
