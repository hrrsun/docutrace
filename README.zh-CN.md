# DocuTrace · 本地可核验文档问答引擎

**每个答案都必须能回溯到页、表行、段落或工作表 —— 否则不返回。**

[English](README.md) | 中文

---

## 为什么做这个

企业文档问答同时卡在两个条件上，能一起满足的方案很少：

1. **数据不能出内网** —— 云端大模型 API 直接出局；
2. **不能核对的答案没有价值** —— 一段总结不是证据，页码加表行才是。

DocuTrace 先解决第二条：全本地 Ollama 推理，自研混合召回排序，每句生成结果附引用账本，引用解析不了就拒绝输出。

## 能力

**证据定位**
- 解析层保留来源坐标：页码、表序号、行号、段落 id、工作表名与单元格范围。
- 输出 `[S#]` 引用标记，与预算账本逐条对应；解析失败的引用不进入展示。

**不依赖向量服务的混合召回**
- BM25 与字符 n-gram 哈希向量分别排序，再用 RRF（倒数排名融合）合并。
- FAISS 不可用时降级为 NumPy 精确相似度，降级状态在界面显式提示，不静默失败。

**上下文预算**
- 按字节记账；完整表行不拆分。
- 单个表行超过剩余预算时整行跳过，并记录该决策。

**隐私与隔离**
- AES-GCM 可逆脱敏：Scrypt（n=2^15, r=8, p=1）派生密钥 + AAD 绑定；脱敏后做残留值扫描；未知标记直接阻断还原，不泄露密文。
- 账号级工作区隔离，跨租户访问返回 403/404，而不是空结果。
- 可选容器沙箱：无网络、无挂载、只读根、非 root，0.5 CPU / 128 MiB / 12 s。

## 架构

```
 ingest.py                 engine.py                      local_model.py
┌──────────────────┐   ┌────────────────────────┐   ┌────────────────────┐
│ PDF / DOCX       │   │ BM25  ─┐               │   │ Ollama /api/chat   │
│ XLSX / CSV / MD  │──▶│ n-gram ─┴─▶ RRF ─▶ top-k│──▶│ /api/embed         │
│ → Unit[]         │   │ 上下文预算账本          │   │ （仅本机）          │
└──────────────────┘   └────────────────────────┘   └────────────────────┘
        │                         │                          │
        └───────────┬─────────────┴──────────────┬───────────┘
                    ▼                            ▼
              studio/api.py                 app.py / cli.py
        FastAPI：工作区、脱敏、沙箱、重排     Streamlit 界面 + 命令行
```

## 快速开始

需要 Python 3.11+；生成阶段需要本机 Ollama（纯检索模式不需要）。

```bash
python -m pip install -r requirements-tested.txt
python -m streamlit run app.py --server.address 127.0.0.1
```

命令行（纯检索）：

```bash
python cli.py examples/spec.pdf -q "What is BETA pressure?"
python cli.py examples/spec.pdf -q "What is BETA pressure?" --model qwen3:30b-a3b
```

回归验证：

```bash
python -m ruff check .
python -m pytest -q
python demo.py --report evaluation.json
```

## 评测

`demo.py --report` 在合成样例文档上跑 6 题标注集，结果写入 `evaluation.json`：

| 召回方式 | Hit@1 | Hit@3 |
| --- | --- | --- |
| 关键词（BM25） | 1.00 | 1.00 |
| 向量（字符 n-gram） | 1.00 | 1.00 |
| 混合（RRF） | 1.00 | 1.00 |

**如实说明**：6 道合成题是冒烟测试，不是 benchmark。它验证的是引用链路接对了、混合融合没有破坏关键词召回。真实文档盲测是下一个里程碑，见「边界」。

回归：`pytest` 22 项通过；`tools/` 下验收脚本覆盖权限、加密、沙箱边界（11 项）。

## 边界

这些边界提前写清，因为它们决定了上面所有数字的适用范围：

- **不做 OCR**。无文本层扫描件会被明确提示，而不是硬解析出错误内容。
- **不处理嵌套表与合并单元格推断**。复杂版式退化为段落级证据。
- **盲测未做**。真实文档上的召回质量尚未测量，公开数字全部基于合成数据。
- **单机单租户规模**。工作区隔离在应用层实现，不是数据库集群级隔离。
- **仅本机模型**。不提供云厂商适配器，这是设计上的取舍。

## 目录

```
app.py            Streamlit 界面
cli.py            命令行入口
engine.py         混合召回、RRF 融合、上下文预算
ingest.py         PDF / OOXML / CSV 解析为带坐标的单元
local_model.py    Ollama 客户端（仅本机，不走代理、不跟随重定向）
studio/           FastAPI 服务：api、store、privacy、rerank、沙箱执行
tests/            回归测试
tools/            验收脚本（权限 / 加密 / 沙箱）
examples/         合成样例文档
deploy/           Docker Compose 参考部署
```

## 背景

个人工程项目。架构设计、验收标准、测试设计与集成由作者完成；早期部分实现使用 AI 结对编程生成并逐行复核。这一点明确写出，方便评审据此权衡代码 —— 可验证的是设计与验收证据，不是敲键盘的次数。

## 许可

MIT，见 [LICENSE](LICENSE)。
