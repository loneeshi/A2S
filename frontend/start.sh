#!/bin/bash

# Agent Visualization Frontend - 快速启动脚本

echo "=========================================="
echo "  Agent Visualization Frontend"
echo "  De-blackboxing Swarm Systems"
echo "=========================================="
echo ""

# 检查 Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js 未安装"
    echo "请访问 https://nodejs.org/ 下载安装"
    exit 1
fi

echo "✅ Node.js 版本: $(node --version)"
echo ""

# 进入前端目录
cd "$(dirname "$0")"

# 检查依赖
if [ ! -d "node_modules" ]; then
    echo "📦 安装依赖..."
    npm install
    echo ""
fi

# 检查端口 5173
if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  端口 5173 已被占用"
    echo "尝试关闭占用端口的进程..."
    lsof -ti:5173 | xargs kill -9 2>/dev/null || true
    sleep 1
fi

echo "🚀 启动开发服务器..."
echo ""
echo "访问地址:"
echo "  → http://localhost:5173"
echo ""
echo "按 Ctrl+C 停止服务器"
echo ""
echo "=========================================="
echo ""

npm run dev
