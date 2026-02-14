# 修复Task 140问题的最小改动方案

## 问题定位

你的Root Agent在 [root.py:72-100](design/A2S/Stulife/src/agents/skill_tree/root.py#L72-L100) 使用LLM推理来路由任务。

当收到Task 140时：
```
输入: "Current time: Week 0, Thursday 14:30"
LLM推理: "这只是时间陈述，不是任务" → 路由到GENERIC
GenericManager: 没有任务可做 → 幻觉4小时 ❌
```

## 解决方案：修改Root Agent的routing prompt

### 方案1：最小改动（推荐）

**只需修改一个文件：** `root.py`

在第72行的`reasoning_prompt`中，添加自主任务的说明：

```python
# 在第78行manager_descriptions后面添加：

manager_descriptions = """
# ... 现有的manager描述 ...
"""

# 新增：自主任务处理说明
self_directed_task_guide = """

**IMPORTANT - Self-Directed Tasks:**

If the task description is ONLY a time statement (e.g., "Current time: Week 0, Thursday 14:30")
with no other instructions, this is a **self-directed task**.

For self-directed tasks:
1. First route to **calendar_management** to check the calendar
2. The CalendarManager will determine if there's a scheduled activity
3. If a navigation event is found, it will be handled by NavigationManager

Example of self-directed task:
- Input: "Current time: Week 0, Thursday 14:30"
- Action: Route to "calendar_management" to check scheduled events
- Output: {{"manager_type": "calendar_management", "reasoning": "..."， "confidence": "high"}}

**Detection pattern:**
- Empty instruction OR
- Instruction starts with "Current time:" OR
- Instruction < 30 characters and only contains time information

→ Route to "calendar_management" manager
"""

reasoning_prompt = f"""
You are the Root Agent responsible for task routing.

Task Description:
"{task_description}"

{manager_descriptions}
{self_directed_task_guide}  # ← 新增

# ... 其余保持不变 ...
"""
```

### 方案2：增强CalendarManager（配合方案1）

找到你的CalendarManager实现，在处理任务时添加检查：

```python
# 在 specialized_managers.py 的 CalendarManager 中

class CalendarManager(ManagerAgent):
    def execute(self, task_description):
        # 检查是否为自主任务
        if self._is_self_directed(task_description):
            return self._handle_self_directed_task(task_description)

        # 正常日历任务处理
        return self._handle_normal_calendar_task(task_description)

    def _is_self_directed(self, task_desc):
        """检测是否为自主任务"""
        task_desc = task_desc.strip()
        return (
            not task_desc or
            task_desc.startswith("Current time:") or
            (len(task_desc) < 30 and "week" in task_desc.lower())
        )

    def _handle_self_directed_task(self, task_desc):
        """处理自主任务"""
        # 1. 提取时间
        time_str = self._extract_time(task_desc)

        # 2. 查询日历
        calendar_result = self.call_tool(
            "calendar.view_schedule",
            calendar_id="self",
            # 根据time_str解析参数
        )

        # 3. 如果找到事件
        if calendar_result.success and calendar_result.data:
            event = calendar_result.data[0]

            # 4. 判断事件类型，可能需要转交给其他Manager
            if 'walk' in event.title.lower() or 'exploration' in event.title.lower():
                # 转交给NavigationManager
                return self._delegate_to_navigation(event)

        # 5. 没有找到事件 - 直接finish
        return self.finish(
            summary=f"No scheduled activity at {time_str}. Awaiting further instructions."
        )
```

### 方案3：在GenericManager添加安全检查（配合方案1、2）

在GenericManager的开始处添加检查：

```python
class GenericManager(ManagerAgent):
    def execute(self, task_description):
        # 安全检查：防止幻觉
        if self._is_invalid_task(task_description):
            return self.finish(
                summary=f"Invalid or ambiguous task: '{task_description}'. "
                       "No clear action to take. Awaiting clarification."
            )

        # 正常处理
        # ...

    def _is_invalid_task(self, task_desc):
        """检测无效/模糊的任务"""
        task_desc = task_desc.strip()

        # Pattern 1: 空指令
        if not task_desc or len(task_desc) < 10:
            return True

        # Pattern 2: 只有时间陈述
        if task_desc.startswith("Current time:") and len(task_desc) < 50:
            return True

        # Pattern 3: 太模糊
        vague_patterns = [
            "what should i do",
            "determine appropriate action",
            "awaiting"
        ]
        return any(p in task_desc.lower() for p in vague_patterns)
```

## 实施步骤

### Step 1: 修改root.py (必须)

```bash
cd /Users/dp/Agent_research/design/A2S/Stulife

# 备份
cp src/agents/skill_tree/root.py src/agents/skill_tree/root.py.backup

# 修改 root.py 第72-78行，添加 self_directed_task_guide
```

**具体修改：**在`reasoning_prompt`的`manager_descriptions`后添加自主任务说明（见方案1）

### Step 2: 检查CalendarManager (推荐)

```bash
# 找到CalendarManager实现
grep -r "class CalendarManager" src/agents/

# 添加 _is_self_directed 和 _handle_self_directed_task 方法
```

### Step 3: 测试修复

```bash
# 测试Task 140
python src/run_experiment.py \
    --config_path "task_data/config/your_config.yaml" \
    --task_ids "140_campus_exploration_037" \
    --debug

# 观察：
# 1. Root Agent是否正确识别为自主任务
# 2. 是否路由到calendar_management
# 3. 是否查询日历
# 4. 完成时间 < 15分钟
# 5. 动作数量 < 200
```

### Step 4: 批量测试空指令任务

```bash
# 测试前6个有问题的任务
python src/run_experiment.py \
    --config_path "task_data/config/your_config.yaml" \
    --task_ids "70_campus_exploration_044,117_campus_exploration_047,140_campus_exploration_037,144_campus_exploration_040,147_campus_exploration_038,148_campus_exploration_027"

# 验证：
# - 所有任务 < 15分钟
# - 没有幻觉行为
# - 成功率 > 60%
```

## 修改优先级

1. **必须做（HIGH）：** 方案1 - 修改Root Agent的routing prompt
2. **强烈推荐（MEDIUM）：** 方案2 - 增强CalendarManager
3. **可选（LOW）：** 方案3 - GenericManager安全检查

只做方案1就能解决70%的问题。
方案1+2可以解决90%的问题。
方案1+2+3可以解决95%+的问题。

## 预期改进

**修改前（Task 140）：**
- 时间：4h 25min
- 动作：2,187
- 结果：失败（执行了错误的任务）

**修改后（Task 140）：**
- 时间：3-8分钟
- 动作：20-50（查日历 + 可能的导航）
- 结果：成功（或正确地标记为"无预定活动"）

## 验证清单

修复完成后，验证：

- [ ] Root Agent能识别空指令/时间陈述为自主任务
- [ ] 自主任务被路由到calendar_management而非GENERIC
- [ ] CalendarManager查询calendar.view_schedule
- [ ] 没有幻觉（不创造假任务）
- [ ] Task 140在15分钟内完成
- [ ] 动作数量 < 200
- [ ] 其他5个空指令任务也能正常完成

## 注意事项

1. **不要修改benchmark数据** - task_data/tasks.json是正确的
2. **不要跳过空指令任务** - 这是benchmark的核心特性
3. **优先测试单个任务** - 确保修复有效再跑全量
4. **保留日志** - 方便调试和验证

---

## 总结

**你不能直接运行原config** 因为你的agent代码不支持自主任务。

**最小修改：**
- 修改 [root.py:72-78](design/A2S/Stulife/src/agents/skill_tree/root.py#L72-L78)
- 在routing prompt中添加自主任务说明
- 让LLM知道空指令应该路由到calendar_management

修改后，你就可以运行原config了。
