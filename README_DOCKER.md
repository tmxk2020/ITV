# IPTV 智能整理平台 Docker 部署指南

支持 **x86_64** 和 **ARM64** (如树莓派、Apple Silicon) 架构。

## 快速开始

### 1. 克隆或下载项目

```bash
git clone <your-repo> iptv-collector
cd iptv-collector

2. 构建镜像
方法一：使用脚本（推荐）
bash
chmod +x build.sh
./build.sh

方法二：直接使用 docker-compose
bash
docker-compose build

3. 运行容器
一次性运行（采集一次后退出）
修改 docker-compose.yml 中环境变量 RUN_MODE=once，然后：
docker-compose up

定时运行（默认每6小时采集一次）
docker-compose up -d

查看日志：
docker logs -f iptv-collector

4. 获取结果
采集完成后，输出文件位于 ./output/ 目录：

tv.m3u – M3U 播放列表

tv.txt – 频道名+URL 列表

shai.txt – 未匹配频道记录

stats.json – 统计信息

可直接用播放器打开 tv.m3u，或通过 Web 服务器分享。

5. 自定义配置
修改采集频率
编辑 docker-compose.yml，设置 SCHEDULE_INTERVAL（单位秒），例如 43200 为12小时。

修改 IPTV 源
编辑 src/config.py 中的 IPTV_SOURCES 列表，或挂载自定义 config.py。

使用环境变量文件
复制 .env.example 为 .env，填入需要的值，然后在 docker-compose.yml 中添加：
    env_file:
      - .env

6. 多架构说明
Docker Hub 官方 python:3.10-slim-bookworm 镜像支持 amd64, arm64, arm/v7。

ffmpeg 在 Debian 仓库中提供多架构版本。

本项目默认构建当前主机的架构。若要同时构建多个架构并推送到仓库，可使用 docker buildx。

示例多架构构建并推送（需先创建 builder）：
docker buildx create --name multiarch --use
docker buildx build --platform linux/amd64,linux/arm64 -t yourname/iptv-collector:latest --push .

7. 故障排查
容器启动后立即退出
检查日志：docker logs iptv-collector

确保 alias.txt、blacklist.txt、demo.txt 存在于项目根目录。

数据库权限错误
如果你以非 root 用户运行，可以在 entrypoint.sh 中添加 chown 命令。

网络问题导致依赖安装失败
使用代理或修改 Docker 守护进程的 DNS 设置。

致谢
本项目基于开源 IPTV 收集工具构建，仅供学习研究使用。


---

### 额外：支持多架构自动适配的 entrypoint.sh（优化版）

```bash
#!/bin/bash
set -e

echo "=========================================="
echo "IPTV 智能整理平台 Docker 容器启动"
echo "检测到架构: $(uname -m)"
echo "=========================================="

mkdir -p /app/data /app/output
cd /app

# 更新 IP 数据库（首次或文件不存在/无效时）
if [ ! -f /app/qqwry.dat ] || [ "$(stat -c %s /app/qqwry.dat 2>/dev/null || echo 0)" -lt 1048576 ]; then
    echo "正在更新 IP 数据库..."
    python -m src.update_ipdb || echo "⚠️ IP 数据库更新失败，将使用已有文件（如有）"
fi

RUN_MODE=${RUN_MODE:-once}

if [ "$RUN_MODE" = "once" ]; then
    echo "执行一次性采集任务..."
    python -m src.run
    echo "任务完成，容器即将退出。"
    exit 0
elif [ "$RUN_MODE" = "schedule" ]; then
    INTERVAL=${SCHEDULE_INTERVAL:-21600}
    echo "启动定时模式，每 ${INTERVAL} 秒执行一次"
    while true; do
        echo "$(date): 开始采集任务..."
        python -m src.run
        echo "$(date): 任务完成，等待 ${INTERVAL} 秒后继续..."
        sleep $INTERVAL
    done
else
    echo "未知的运行模式: $RUN_MODE，请设置为 once 或 schedule"
    exit 1
fi

最终项目结构（添加了 Docker 相关文件）
iptv-smart-collector/
├── .dockerignore
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── build.sh
├── entrypoint.sh
├── README_DOCKER.md
├── README.md (原有)
├── alias.txt
├── blacklist.txt
├── demo.txt
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── alias_matcher.py
│   ├── blacklist_filter.py
│   ├── classifier.py
│   ├── config.py
│   ├── database.py
│   ├── demo_filter.py
│   ├── fetcher.py
│   ├── ffmpeg_validator.py
│   ├── generator.py
│   ├── ip_resolver.py
│   ├── logger.py
│   ├── merger.py
│   ├── parser.py
│   ├── run.py
│   ├── speed_tester.py
│   └── update_ipdb.py
└── output/ (自动生成)
