# ALFWorld 数据下载和配置指南

## 问题诊断

运行测试时发现：
```
❌ ALFWorld data not found: /Users/dp/.alfworld/alfred/data/json_2.1.1/train
```

## 解决方案：下载ALFWorld数据

### 步骤1：下载ALFWorld游戏数据

```bash
# 激活conda环境
conda activate skilltree_py311

# 方法1：使用alfworld-agenerate脚本（推荐）
alfworld-agenerate --download-data

# 方法2：手动下载
# 访问 https://github.com/alfworld/alfworld#download-alfred-data
# 下载并解压到 ~/.alfworld/
```

### 步骤2：验证数据安装

```bash
ls -la ~/.alfworld/alfred/data/json_2.1.1/
# 应该看到：train/, valid_in_distribution/, valid_out_of_distribution/
```

### 步骤3：更新测试配置

我已经更新了`scripts/test_alfworld_real.py`，添加了完整的配置参数：

```python
config = {
    'env': {
        'type': 'AlfredTWEnv',
        'goal_desc_human_anns_prob': 0,
        'task_types': [1],  # 1=pick_and_place_simple
    },
    'dataset': {
        'data_path': '~/.alfworld/alfred/data/json_2.1.1/train',
        'eval_id_data_path': '~/.alfworld/alfred/data/json_2.1.1/valid_in_distribution',
        'eval_ood_data_path': '~/.alfworld/alfred/data/json_2.1.1/valid_out_of_distribution',
        'num_train_games': -1,  # -1 = use all games
        'num_eval_games': -1,
    }
}
```

### 可用任务类型

- 1: `pick_and_place_simple` - 简单的抓取和放置
- 2: `look_at_obj_in_light` - 在灯光下查看物体
- 3: `pick_clean_then_place_in_recep` - 清洁后放置
- 4: `pick_heat_then_place_in_recep` - 加热后放置
- 5: `pick_cool_then_place_in_recep` - 冷却后放置
- 6: `pick_two_obj_and_place` - 抓取两个物体并放置

## 完整测试流程

数据下载完成后：

```bash
conda activate skilltree_py311
cd /Users/dp/Agent_research/design/auto_expansion_agent

# 运行测试
python scripts/test_alfworld_real.py --num_episodes 5
```

## 如果没有数据文件

### 临时方案：使用模拟测试

在真实数据准备好之前，可以继续使用模拟测试：

```bash
python scripts/test_alfworld.py  # 模拟测试，不需要ALFWorld数据
```

这会：
- 生成agent tree
- 模拟episode执行
- 测试动态扩展机制
- 验证prompt缓存优化

## 数据大小

ALFWorld数据大约需要：
- 训练集：~2GB
- 验证集：~500MB
- 总计：~2.5GB

## 参考链接

- ALFWorld GitHub: https://github.com/alfworld/alfworld
- 数据下载说明: https://github.com/alfworld/alfworld#download-alfred-data
- 论文: https://arxiv.org/abs/2010.04436

## 当前状态

✅ 已完成：
- Agent tree生成
- Prompt缓存优化
- 性能监控
- 动态扩展机制
- 测试框架

⏳ 等待：
- ALFWorld数据下载

💡 建议：
- 先用模拟测试验证框架功能
- 下载ALFWorld数据后再运行真实测试
