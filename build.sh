#!/bin/bash
set -e

echo "=========================================="
echo "IPTV 智能整理平台 Docker 镜像构建"
echo "=========================================="

# 检测架构
ARCH=$(uname -m)
echo "检测到架构: $ARCH"

# 镜像名称和标签
IMAGE_NAME="iptv-collector"
TAG="latest"

# 如果使用 buildx 支持多平台，可以设置 PLATFORMS
# 单架构构建直接使用 docker build
# 如需多平台（如同时构建 amd64/arm64），请取消注释下面的 buildx 命令

# 使用标准 docker build（当前架构）
echo "正在构建 ${IMAGE_NAME}:${TAG} (${ARCH})..."
docker build -t ${IMAGE_NAME}:${TAG} .

# 可选：同时打上架构标签
docker tag ${IMAGE_NAME}:${TAG} ${IMAGE_NAME}:${ARCH}-${TAG}

echo "✅ 构建完成！"
echo "运行容器："
echo "  docker-compose up -d"
echo "或直接运行："
echo "  docker run -d --name iptv-collector -v $(pwd)/data:/app/data -v $(pwd)/output:/app/output ${IMAGE_NAME}:${TAG}"
