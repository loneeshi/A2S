# ALFWorld 数据下载完整指南

## ✅ 正确的下载命令

```bash
conda activate skilltree_py311
alfworld-download --data-dir ~/.alfworld
```

**参数说明**：
- `--data-dir`: 指定下载目录（默认：`~/.cache/alfworld`）
- `--extra`: 同时下载BUTLER agents和Seq2Seq训练文件（可选）
- `-f`, `--force`: 覆盖已存在文件（可选）

## ⚠️ 下载失败解决方案

### 问题：网络连接错误

```
ConnectionError: ('Connection aborted.', ConnectionResetError(54, 'Connection reset by peer'))
```

### 解决方案

#### 方法1：使用VPN或代理
```bash
# 设置代理后运行
export http_proxy=http://your-proxy:port
export https_proxy=http://your-proxy:port

alfworld-download --data-dir ~/.alfworld
```

#### 方法2：从GitHub手动下载
```bash
# 1. 访问ALFWorld GitHub Releases
https://github.com/alfworld/alfworld/releases

# 2. 下载json_2.1.1数据文件
# 通常命名为：alfworld.tgz 或 json_2.1.1.tar.gz

# 3. 解压到指定目录
mkdir -p ~/.alfworld
tar -xzf alfworld.tgz -C ~/.alfworld/
```

#### 方法3：使用镜像站点
```bash
# 从gitee镜像下载（如果有）
# 或使用GitHub镜像加速
```

#### 方法4：暂时使用模拟测试
```bash
# 框架已支持自动回退到模拟模式
python scripts/test_alfworld_real.py --num_episodes 10

# 模拟模式同样测试：
# - Agent tree生成 ✅
# - 性能监控 ✅
# - 动态扩展 ✅
# - Prompt缓存优化 ✅
```

## 📊 数据大小和内容

下载内容：
- **训练数据**：~2GB
- **验证数据**：~500MB
- **总计**：~2.5GB（不含--extra）

包含文件：
- `json_2.1.1/train/` - 训练集游戏
- `json_2.1.1/valid_in_distribution/` - 验证集（同分布）
- `json_2.1.1/valid_out_of_distribution/` - 验证集（外分布）
- 每个游戏包含：`traj_data.json` 等

## 🔄 下载后验证

```bash
# 检查数据是否下载成功
ls -la ~/.alfworld/alfred/data/json_2.1.1/

# 应该看到：
# train/
# valid_in_distribution/
# valid_out_of_distribution/

# 运行测试验证
python scripts/test_alfworld_real.py --num_episodes 3
```

## 💡 临时解决方案

如果暂时无法下载数据，模拟测试模式已经完全可用：

```bash
# 运行模拟测试（无需ALFWorld数据）
python scripts/test_alfworld_real.py --num_episodes 20

# 或运行纯模拟测试
python scripts/test_alfworld.py
```

模拟测试验证了：
- ✅ Benchmark描述读取
- ✅ Agent tree自动生成（5 workers + 2 managers）
- ✅ 性能监控机制
- ✅ 动态扩展触发
- ✅ Prompt缓存优化

## 📚 参考资源

- **ALFWorld GitHub**: https://github.com/alfworld/alfworld
- **论文**: https://arxiv.org/abs/2010.04436
- **文档**: https://alfworld.github.io/

## 🎯 当前状态

✅ **已完成**：
- ALFWorld集成代码
- 完整配置支持
- 自动模拟回退
- 所有框架功能正常

⏳ **待完成**：
- 下载ALFWorld数据文件（~2.5GB）
- 运行真实环境测试

💡 **建议**：
- 先用模拟测试验证框架功能
- 网络稳定时再下载真实数据
- 真实数据准备好后，代码会自动使用

---

**Sources**:
- [ALFWorld实战指南：5步构建跨模态智能体系统](https://m.blog.csdn.net/gitblog_01017/article/details/156322522)
- [ALFWorld 开源项目使用教程](https://m.blog.csdn.net/gitblog_00386/article/details/141236898)
- [ALFWorld技术深度解析](https://m.blog.csdn.net/gitblog_00498/article/details/156322169)
