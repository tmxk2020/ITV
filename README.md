# IPTV 智能测速整理平台

自动聚合多个 IPTV 源，通过 HTTP 探测 + ffmpeg 深度验证过滤无效链接，并按央视、卫视、地方、体育、动漫等分类输出 M3U/TXT 文件，通过 GitHub Actions 每日自动更新并部署到 GitHub Pages。

## 功能特点

- ✅ 多源聚合：同时拉取 6+ 公开 IPTV 源，自动去重
- ✅ 双重验证：快速 HTTP 测速 + ffmpeg 流分析（地理封锁/DRM/纯音频检测）
- ✅ 智能分类：基于频道名和 group-title 自动归类
- ✅ 双格式输出：支持 `/tv.m3u` 和 `/tv.txt` 访问
- ✅ 全自动化：GitHub Actions 每 6 小时运行，缓存依赖大幅减少构建时间
- ✅ 容错重试：指数退避重试机制，应对网络波动

## 部署方法

1. **Fork 本仓库** 到你的 GitHub 账号
2. **启用 GitHub Actions**：仓库 → Actions → 允许工作流
3. **手动触发首次运行**：Actions → `IPTV 源智能更新与整理` → Run workflow
4. 等待 10-20 分钟后访问：
   - `https://你的用户名.github.io/iptv-smart-collector/tv.m3u`
   - `https://你的用户名.github.io/iptv-smart-collector/tv.txt`

## 自定义配置

编辑 `src/config.py` 可以：
- 增删 IPTV 源地址
- 修改分类关键词
- 调整并发数/超时时间
- 关闭 ffmpeg 深度验证（`FFMPEG_ENABLE = False`）

## 更新频率

GitHub Actions 默认每 6 小时运行一次（`0 */6 * * *`），你可以在 `.github/workflows/update_iptv.yml` 中修改 cron 表达式。

## 注意事项

- 本项目仅用于学习研究，请勿用于商业用途
- 所有 IPTV 源均来自公开仓库，不保证长期有效
- ffmpeg 深度验证会增加运行时间，但能有效过滤地理封锁和死链

## 致谢

- [iptv-org/iptv](https://github.com/iptv-org/iptv)
- [Guovin/iptv-api](https://github.com/Guovin/iptv-api)
- [zilong7728/Collect-IPTV](https://github.com/zilong7728/Collect-IPTV)
