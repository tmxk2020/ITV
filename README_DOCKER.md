# IPTV 智能整理平台 Docker 部署指南

下载构建文件压缩包，解压后上传到指定位置，直接运行docker-compose即可

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
