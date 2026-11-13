# 本机企业知识 Agent

使用腾讯 WeKnora v0.9.0 官方 Compose、配置文件与镜像标签。官方平台负责登录、知识库、文档索引、Agent 工具调度和回答引用。项目生成的 Markdown 提供原始文件名、PDF 页码、工作表位置以及活动表全量统计。

## 启动和访问

在项目根目录执行 `.\deploy\weknora\start.ps1`。打开 http://127.0.0.1:18780 。后台健康检查地址为 http://127.0.0.1:18781/health 。首次初始化在部署目录生成 .env，包含数据库密码和加密密钥，请随数据卷一起保管。

进入本机网页注册并登录，在模型设置中选择 Ollama，本机 Docker Desktop 容器访问宿主机的地址为 `http://host.docker.internal:11434`。聊天模型使用 `qwen3:30b-a3b`，embedding 使用 `bge-m3`（1024 维）。选择文档知识库，将这两个本地模型绑定到对应设置。

上传 sample.md，等待解析完成。在智能推理/Agent 对话中选择该知识库，提问“BETA 的压力要求是多少？请列出原始页码和表行。”预期结果为 71 kPa，第 2 页表 1 行 2，并能在引用中看到对应记录。可追加“同一份材料中 ALPHA 的压力是多少？”检查是否引用第 1 页的 17 kPa。

## 导入自己的资料

可直接在平台上传文件。如果需要表格行地址和精确的活动数，可先在项目根目录运行以下任一命令。导出的 Markdown 供网页上传，API 导入使用当前用户显式授权的知识库，不在代码里保存密钥。

```powershell
python weknora_import.py examples/spec.pdf --export spec-evidence.md
python weknora_import.py examples/spec.pdf --kb 知识库ID
```

活动表导出包含全表和各月的记录数。统计按同一文件内的记录、跨年份的同名月份合计；多年度分析需要另外指定年份范围。正文逐行保留文件及位置，可供 Agent 检索核对。

## 运维

在本目录执行 `docker compose -p docagent ps` 检查服务，`docker compose -p docagent stop` 停止。业务资料存入 Docker 命名卷。部署时下载镜像和模型；离线搬迁须另行导出镜像、模型、卷和密钥，并做还原演练。Web 搜索、外部 MCP 和云端模型属于额外的网络能力；本地资料场景请仅启用知识库工具和本地模型。

[上游发布](https://github.com/Tencent/WeKnora/releases/tag/v0.9.0) · [上游部署说明](https://github.com/Tencent/WeKnora/blob/v0.9.0/website-docs/01-getting-started/02-installation.md) · [上游许可证](LICENSE)
