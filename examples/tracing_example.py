"""
全链路追踪系统使用示例

演示如何在 ALFWorld 任务中使用追踪系统，实现"去黑箱化"展示。
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.tracing import (
    TracingManager, NodeType, NodeStatus, EventType,
    PromptCachingInfo, CacheStatus, BenchmarkContext,
    set_global_tracing, get_global_tracing
)


class TracedLLMClient:
    """带追踪的 LLM 客户端示例"""

    def __init__(self, tracing_manager: TracingManager, model: str = "gpt-4"):
        self.tracing = tracing_manager
        self.model = model

    async def chat(
        self,
        node_id: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        LLM 调用（带追踪）

        自动记录：
        - Prompt Caching 信息
        - Token 消耗
        - 响应时间
        - 工具调用
        """
        import time
        start_time = time.time()

        # 模拟 LLM API 调用
        await asyncio.sleep(0.5)  # 模拟网络延迟

        # 模拟响应
        response_content = "I'll navigate to the countertop to find the mug."
        prompt_tokens = sum(len(msg.get("content", "")) for msg in messages) // 4
        completion_tokens = len(response_content) // 4
        total_tokens = prompt_tokens + completion_tokens
        latency_ms = (time.time() - start_time) * 1000

        # 模拟缓存命中（假设部分 prompt 命中缓存）
        cache_info = PromptCachingInfo(
            status=CacheStatus.PARTIAL,
            cache_hit_position=100,  # 从第 100 个 token 开始命中
            cache_hit_tokens=prompt_tokens - 200,  # 命中了大部分
            total_tokens=prompt_tokens,
            cache_key=f"cache_{hash(str(messages)) % 1000}",
            cache_hit_percentage=85.0
        )

        # 记录 LLM 调用
        call_id = await self.tracing.record_llm_call(
            node_id=node_id,
            model=self.model,
            messages=messages,
            response_content=response_content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            tools=tools,
            cache_info=cache_info
        )

        return {
            "content": response_content,
            "call_id": call_id,
            "tokens": total_tokens
        }


class TracedALFWorldAgent:
    """带追踪的 ALFWorld Agent"""

    def __init__(
        self,
        tracing_manager: TracingManager,
        llm_client: TracedLLMClient,
        role: str = "ALFWorldWorker"
    ):
        self.tracing = tracing_manager
        self.llm = llm_client
        self.role = role

    async def execute_task(
        self,
        task_description: str,
        benchmark_context: Dict[str, Any],
        parent_id: Optional[str] = None,
        max_steps: int = 5
    ) -> Dict[str, Any]:
        """
        执行 ALFWorld 任务（带完整追踪）

        追踪内容包括：
        1. Node State: Agent 的 role, system prompt, user messages
        2. Execution Context: Benchmark 上下文、可用命令
        3. Prompt Caching: 每次调用是否命中缓存
        4. Dynamic Memory: 每步的局部记忆快照
        5. Tool Calls: 执行的动作
        6. Handoff Vector: 如果创建子 Agent
        7. Task Trace: 完整的执行过程
        """
        # 创建 Agent 节点
        node_id = await self.tracing.create_node(
            node_type=NodeType.WORKER,
            role=self.role,
            system_prompt=f"""You are an ALFWorld agent tasked with completing household tasks.

Your role: {self.role}

Available tools:
- goto(location): Navigate to a location
- take(object): Pick up an object
- put(object, location): Place an object
- open(object): Open an object/container
- close(object): Close an object/container

Think step by step and plan your actions carefully.""",
            user_messages=[{"role": "user", "content": task_description}],
            tools=[
                {
                    "name": "goto",
                    "description": "Navigate to a location",
                    "parameters": {"type": "object", "properties": {"location": {"type": "string"}}}
                },
                {
                    "name": "take",
                    "description": "Take an object",
                    "parameters": {"type": "object", "properties": {"object": {"type": "string"}}}
                }
            ],
            parent_id=parent_id
        )

        await self.tracing.start_node(node_id)

        try:
            # 记录 Benchmark 上下文
            await self.tracing.record_benchmark_context(
                node_id=node_id,
                benchmark_name=benchmark_context.get("benchmark_name", "alfworld"),
                available_commands=benchmark_context.get("available_commands", []),
                observation=benchmark_context.get("observation"),
                background=benchmark_context.get("background")
            )

            # 记录初始动态记忆
            await self.tracing.record_dynamic_memory(
                node_id=node_id,
                short_term=[task_description],
                long_term=[],
                working={"current_goal": task_description, "completed_steps": []}
            )

            results = []

            # 执行任务步骤
            for step in range(max_steps):
                print(f"\n{'='*60}")
                print(f"Step {step + 1}/{max_steps}")
                print(f"{'='*60}")

                # 构建消息（包含历史）
                messages = [
                    {"role": "system", "content": f"You are {self.role}"},
                    {"role": "user", "content": task_description}
                ]

                # 添加之前的观察
                if "observation" in benchmark_context:
                    messages.append({
                        "role": "user",
                        "content": f"Observation: {benchmark_context['observation']}"
                    })

                # LLM 调用（自动追踪缓存、token、延迟）
                llm_response = await self.llm.chat(
                    node_id=node_id,
                    messages=messages,
                    tools=[
                        {
                            "name": "goto",
                            "description": "Navigate to a location",
                            "parameters": {"type": "object", "properties": {"location": {"type": "string"}}}
                        }
                    ]
                )

                response_content = llm_response["content"]
                print(f"🤖 LLM Response: {response_content}")

                # 解析动作
                action = self._parse_action(response_content)
                print(f"🎯 Action: {action}")

                # 记录工具调用
                await self.tracing.record_tool_call(
                    node_id=node_id,
                    tool_name=action.get("tool", "unknown"),
                    arguments=action.get("arguments", {}),
                    execution_time_ms=50.0,
                    result={"success": True, "observation": "Moved to location"}
                )

                # 更新动态记忆
                await self.tracing.record_dynamic_memory(
                    node_id=node_id,
                    short_term=[response_content, f"Executed: {action}"],
                    long_term=[],
                    working={
                        "current_goal": task_description,
                        "completed_steps": [action],
                        "step_number": step + 1
                    }
                )

                results.append({
                    "step": step + 1,
                    "action": action,
                    "observation": "Success"
                })

                # 模拟反思（Reflection Agent）
                if step > 0 and step % 2 == 0:  # 每两步反思一次
                    await self._perform_reflection(node_id, results)

                # 短暂延迟
                await asyncio.sleep(0.1)

            # 完成任务
            await self.tracing.complete_node(node_id, success=True)

            return {
                "node_id": node_id,
                "success": True,
                "steps": results
            }

        except Exception as e:
            await self.tracing.complete_node(node_id, success=False)
            raise e

    def _parse_action(self, response: str) -> Dict[str, Any]:
        """解析 LLM 响应为动作"""
        # 简单解析（实际应用中会更复杂）
        if "goto" in response.lower():
            return {"tool": "goto", "arguments": {"location": "countertop"}}
        elif "take" in response.lower():
            return {"tool": "take", "arguments": {"object": "mug"}}
        else:
            return {"tool": "look", "arguments": {}}

    async def _perform_reflection(self, node_id: str, results: List[Dict]) -> None:
        """执行反思（Reflection Agent）"""
        print("\n🤔 Reflection Agent analyzing...")

        await self.tracing.record_reflection(
            node_id=node_id,
            trigger_reason="periodic_review",
            reflection_content="Progress is good, but navigation could be more efficient.",
            suggested_improvements=[
                "Consider planning the full path before moving",
                "Keep track of visited locations to avoid loops"
            ],
            confidence_score=0.85,
            reflection_time_ms=150.0,
            llm_calls=1,
            tokens_used=200
        )


async def main():
    """主函数：演示完整的追踪流程"""

    print("="*80)
    print("ALFWorld Agent Execution with Full Tracing")
    print("="*80)

    # 1. 创建追踪管理器
    tracing = TracingManager(
        task_name="ALFWorld_Navigation_Task",
        task_description="Navigate to countertop and take mug 1",
        output_dir="./results/tracing_example",
        auto_save=True
    )

    # 设置为全局追踪器
    set_global_tracing(tracing)

    # 2. 创建带追踪的 LLM 客户端
    llm_client = TracedLLMClient(tracing, model="gpt-4")

    # 3. 创建 Agent
    agent = TracedALFWorldAgent(tracing, llm_client, role="ALFWorldWorker")

    # 4. 执行任务（自动追踪）
    benchmark_context = {
        "benchmark_name": "alfworld",
        "task_type": "pick_and_place",
        "available_commands": [
            "goto countertop 1",
            "take mug 1",
            "put mug 1 in diningtable 1"
        ],
        "observation": "You are in a kitchen. You see: countertop 1, cabinet 1, microwave 1",
        "background": "Task: Go to countertop 1 and take mug 1"
    }

    print("\n🚀 Starting task execution with tracing...\n")

    result = await agent.execute_task(
        task_description="Go to countertop 1 and take mug 1",
        benchmark_context=benchmark_context,
        max_steps=3
    )

    # 5. 完成追踪
    await tracing.finalize(
        success=True,
        final_result={
            "task": "Navigate and take object",
            "steps_completed": len(result["steps"]),
            "node_id": result["node_id"]
        }
    )

    print("\n" + "="*80)
    print("✅ Task completed with full tracing!")
    print("="*80)

    # 6. 输出追踪结果摘要
    print("\n📊 Tracing Statistics:")
    stats = tracing.get_statistics()
    print(json.dumps(stats, indent=2))

    print("\n📁 Results saved to:")
    output_dir = Path("./results/tracing_example")
    for file in output_dir.glob("trace_*.json"):
        print(f"  - {file.name}")

    # 7. 输出执行树（用于前端可视化）
    print("\n🌳 Execution Tree (for frontend visualization):")
    tree = tracing.get_execution_tree()
    print(json.dumps(tree, indent=2))

    return tracing


if __name__ == "__main__":
    tracing = asyncio.run(main())

    # 额外演示：如何从文件读取追踪数据
    print("\n" + "="*80)
    print("💡 Demonstrating how to read and visualize trace data")
    print("="*80)

    # 读取完整的追踪数据
    trace_file = Path("./results/tracing_example/trace_*.json")
    if trace_file.exists():
        with open(trace_file, 'r') as f:
            trace_data = json.load(f)
        print("\n📖 Full trace data loaded")
        print(f"   Total nodes: {len(trace_data['all_nodes'])}")
        print(f"   Total events: {len(trace_data['events'])}")
