# ALFWorld Testing Instructions

由于conda环境在当前shell中无法直接访问，请按以下步骤手动测试：

## 方法1：直接在conda环境中运行（推荐）

```bash
# 1. 激活conda环境
conda activate skilltree_py311

# 2. 进入项目目录
cd /Users/dp/Agent_research/design/auto_expansion_agent

# 3. 运行测试（3个episodes）
python scripts/test_alfworld_real.py --num_episodes 3

# 或者运行更多episodes
python scripts/test_alfworld_real.py --num_episodes 10
```

## 方法2：使用完整Python路径

如果你知道conda环境中的Python完整路径，可以创建一个快捷脚本：

```bash
# 首先找到Python路径（在激活的conda环境中运行）
which python
# 输出类似：/Users/dp/xxx/anaconda3/envs/skilltree_py311/bin/python

# 然后直接使用该路径运行测试
/Users/dp/xxx/anaconda3/envs/skilltree_py311/bin/python scripts/test_alfworld_real.py --num_episodes 3
```

## 方法3：提供Python路径给我们

如果你能提供skilltree_py311环境中Python的完整路径，我们可以创建一个自动运行的脚本。

请运行：
```bash
conda activate skilltree_py311
which python
```

然后把Python路径告诉我们，我会更新测试脚本。

## 当前状态

✅ 已完成：
- ALFWorld benchmark配置
- 测试脚本（使用get_environment API）
- Agent tree生成
- 性能监控和动态扩展

⏳ 待测试：
- 真实ALFWorld环境中的实际运行
- 性能指标收集
- 动态扩展验证

## 如果测试成功

测试成功后，你将看到：

1. **Phase 1**: ALFWorld环境初始化
2. **Phase 2**: 生成Agent Tree（5个workers + 2个managers）
3. **Phase 3**: 性能监控器初始化
4. **Phase 4**: 运行真实episodes
5. **Phase 5**: 性能分析
6. **Phase 6**: 动态扩展（如果需要）

输出示例：
```
✅ Completed 3 real episodes
Success rate: 2/3 (66.7%)
Overall success rate: 66.67%
```
