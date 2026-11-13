# 工程依据与验证记录

调研日期为 2026-11-11。下表区分参考文献的结论、本项目采用的设计及其验证边界。

| 来源 | 对项目的影响 |
| --- | --- |
| IBM Research, [Docling Technical Report](https://research.ibm.com/publications/docling-technical-report) | 论文将布局分析和表格结构识别单独建模。当前用确定性行列规则做低成本基线。后续可在同一批盲测文档上比较模型解析的收益。 |
| Docling 项目于 2026-11-09 发布 [docling-parse v7.25.0](https://github.com/docling-project/docling-parse/releases/tag/v7.25.0) | 本次更新涉及 tagged PDF 结构树与单元格映射、字体解码和文本分段。后续应将有结构标签与无标签的 PDF 分组评测。 |
| Liu 等，[Lost in the Middle](https://arxiv.org/abs/2307.03172) | 长上下文中的证据位置会影响任务表现。当前提供候选裁剪与可见预算。尚未评测改变证据顺序对本机模型正确率的影响。 |
| [Attribute or Abstain，EMNLP 2024](https://aclanthology.org/2024.emnlp-main.463/) | 回答、引用和无依据时的行为应分别测量。当前仅校验引用编号合法性；实体、数值和单位的支持关系需要额外标注。 |
| [NIST SSDF](https://csrc.nist.gov/projects/ssdf) 与 [OWASP 提示注入防护](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html) | 文档按不可信数据处理；限制文件与解压大小；模型无宿主执行权限；记录顶层依赖版本并提供可执行回归。此处是工程参考，未做标准符合性审计。 |

## 集成验收

| 检查对象 | 验证方式和证据 |
| --- | --- |
| 文档 → 检索 | 生成 PDF、DOCX、XLSX、CSV 四个样本，6 道标注题同时比对来源、位置和期望值。见 evaluation.json。 |
| 混合检索 → 上下文 | 测试表行保真、重复片段、预算不足、显式用户偏好、无匹配查询。三种检索策略使用相同样本。 |
| 上下文 → Ollama | 在本机向 qwen3:30b-a3b 发送合成 PDF 问题，收到“[S1] BETA pressure is 71 kPa.”，S1 对应第 2 页表 1 行 2。本次实际输入 260 token，预算账本含输出和模板预留共 1374 单位。 |
| Web | Streamlit AppTest 启动主页面；检索、解析及模型调用通过共享模块分别验收。 |
| 安全边界 | 回归覆盖 Docker 不可用时禁止宿主执行，检查关键容器参数。当前主机 Docker Linux 引擎不可达；真实容器阻网、超时清理及内存限制仍待动态验收。 |

未验证真实客户数据质量、语义嵌入模型效果、商业收益和低配机器性能。上面的实测仅针对当前机器与合成数据。

