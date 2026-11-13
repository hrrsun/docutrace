"""Generate a project-specific process register, without inventing approval evidence."""

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "docs"
groups = [
    ("10", "启动", ["项目授权", "参与方识别"]),
    (
        "11",
        "规划",
        [
            "管理总计划",
            "范围管理规则",
            "需求获取",
            "范围定义",
            "工作分解",
            "进度规则",
            "工作活动",
            "依赖排序",
            "工期估算",
            "进度安排",
            "费用规则",
            "费用估算",
            "预算编制",
            "质量规划",
            "资源规划",
            "资源估算",
            "沟通安排",
            "风险规则",
            "风险识别",
            "风险分级",
            "风险量化",
            "风险应对",
            "采购规划",
            "参与安排",
        ],
    ),
    (
        "12",
        "执行",
        [
            "实施协调",
            "知识沉淀",
            "质量改进",
            "资源获取",
            "团队建设",
            "团队管理",
            "信息沟通",
            "应对落实",
            "采购实施",
            "参与协调",
        ],
    ),
    (
        "13",
        "监控",
        [
            "质量检查",
            "交付确认",
            "范围检查",
            "进度检查",
            "费用检查",
            "资源检查",
            "沟通检查",
            "风险复查",
            "采购检查",
            "参与复查",
            "综合绩效",
            "变更决策",
        ],
    ),
    ("14", "收尾", ["阶段关闭"]),
]
outputs = [
    "项目章程及假设",
    "干系人登记",
    "管理计划及三类基准",
    "范围及需求管理计划",
    "需求规格及追踪矩阵",
    "范围说明",
    "WBS及工作包字典",
    "进度管理计划",
    "活动清单及属性",
    "依赖网络",
    "工期估算及依据",
    "计划与进度基准",
    "成本管理计划",
    "成本估算及依据",
    "成本基准及资金安排",
    "质量计划及指标",
    "资源计划及团队规则",
    "资源需求及分解",
    "沟通计划",
    "风险管理计划",
    "风险登记",
    "风险排序报告",
    "定量分析及假设",
    "风险应对方案",
    "采购计划及采购文件",
    "干系人参与计划",
    "实施成果及工作绩效数据",
    "经验教训登记",
    "质量报告及改进记录",
    "人员及设备分派",
    "团队评价",
    "团队问题及调整",
    "沟通记录",
    "应对执行记录",
    "供应商选择及协议",
    "干系人沟通记录",
    "检查测量及核实成果",
    "验收决定",
    "范围偏差分析",
    "进度偏差分析",
    "费用偏差分析",
    "资源偏差分析",
    "沟通效果记录",
    "风险更新及审计",
    "采购检查及关闭记录",
    "参与效果记录",
    "绩效报告",
    "批准或拒绝的变更及日志",
    "移交成果及最终报告",
]
mapping = (
    ["02-initiation.md"] * 2
    + ["03-management-plan.md"] * 24
    + ["05-execution.md"] * 10
    + ["06-control.md"] * 12
    + ["07-closeout.md"]
)
rows = []
for chapter, group, names in groups:
    for section, name in enumerate(names, 1):
        i = len(rows)
        rows.append(
            dict(
                id=f"{chapter}.{section}",
                group=group,
                project_activity=name,
                proposed_output=outputs[i],
                document=mapping[i],
                status="草案或待执行",
                approval="未取得",
                evidence="见对应文档；执行后补记录",
            )
        )
assert len(rows) == 49 and len(outputs) == 49
with (ROOT / "process-register.csv").open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
(ROOT / "process-map.md").write_text(
    "# 49 个过程的项目映射\n\n编号与出版社目录章节对应。活动和产物为本项目裁剪设计，尚未核验教材正文的全部 ITTO。每个正式基准需获得负责人确认。\n\n"
    + "| 教材位置 | 过程组 | 项目活动 | 拟形成产物 | 工作文件 |\n|---|---|---|---|---|\n"
    + "\n".join(
        f"| {r['id']} | {r['group']} | {r['project_activity']} | {r['proposed_output']} | [{r['document']}]({r['document']}) |"
        for r in rows
    ),
    encoding="utf-8",
)

deliveries = [
    ("D01", "调研与可行性", "01-research.md", "草案"),
    ("D02", "项目章程与假设", "02-initiation.md", "待批准"),
    ("D03", "干系人登记", "02-initiation.md", "草案"),
    ("D04", "管理计划和范围", "03-management-plan.md", "待批准"),
    ("D05", "WBS与工作包", "03-management-plan.md", "待批准"),
    ("D06", "工期估算与进度", "03-management-plan.md", "待批准"),
    ("D07", "成本估算与预算", "03-management-plan.md", "待批准"),
    ("D08", "质量及资源计划", "03-management-plan.md", "草案"),
    ("D09", "沟通与风险计划", "03-management-plan.md", "草案"),
    ("D10", "采购和参与计划", "03-management-plan.md", "草案"),
    ("D11", "需求规格与追踪", "04-requirements-design.md", "部分实现"),
    ("D12", "架构及接口设计", "04-requirements-design.md", "集成中"),
    ("D13", "数据和安全设计", "04-requirements-design.md", "待动态验证"),
    ("D14", "代码与依赖版本", "../requirements-tested.txt", "已形成"),
    ("D15", "部署配置", "../deploy/weknora/README.md", "已形成"),
    ("D16", "知识和经验教训", "05-execution.md", "持续更新"),
    ("D17", "工作绩效数据", "05-execution.md", "待连续登记"),
    ("D18", "质量报告", "evidence/pytest.txt", "本轮实测"),
    ("D19", "团队和沟通记录", "05-execution.md", "待实际活动"),
    ("D20", "问题风险变更登记", "06-control.md", "已形成"),
    ("D21", "绩效与偏差报告", "06-control.md", "待基准和实绩"),
    ("D22", "实验和测试计划", "08-test-plan.md", "草案"),
    ("D23", "盲测及引用报告", "08-test-plan.md", "待真实实验"),
    ("D24", "配置发布回退", "03-management-plan.md", "待恢复验证"),
    ("D25", "用户管理员培训", "07-closeout.md", "待执行"),
    ("D26", "验收与移交记录", "07-closeout.md", "待执行"),
    ("D27", "最终报告和归档", "07-closeout.md", "待执行"),
    ("D28", "客户采购合同", "03-management-plan.md", "未发生"),
    ("D29", "独立监理记录", "00-index.md", "未委任，待适用性确认"),
]
with (ROOT / "delivery-register.csv").open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["ID", "交付项", "位置", "状态"])
    w.writerows(deliveries)
with (ROOT / "traceability.csv").open("w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["需求", "实现位置", "测试", "验收条件", "状态"])
    w.writerows(
        [
            [
                "R01",
                "ingest.py;weknora_import.py",
                "T12",
                "同一版本可恢复且不重复入库",
                "哈希持久化及幂等未实现",
            ],
            ["R02", "ingest.py", "T01-T03", "字段和原页一致，失败有提示", "基础样例通过"],
            [
                "R03",
                "deploy/weknora",
                "T09;T11;T12",
                "原生页面上传问答并隔离权限",
                "平台已部署，完整验收待执行",
            ],
            [
                "R04",
                "engine.py;deploy/weknora/tools/server.py",
                "T07;T08",
                "策略实际进入模型请求且预算可观测",
                "独立模块已实现，Agent调用待验",
            ],
            [
                "R05",
                "sandbox.py;deploy/weknora/tools/server.py",
                "T06;T10;T14;T15",
                "计算依据和单位可核对，异常受限",
                "集成中",
            ],
            [
                "R06",
                "activity.py",
                "T04;T05",
                "全部授权记录参与统计",
                "活动模式已验证，通用表待实现",
            ],
        ]
    )

# Independent review units retain the actual current draft, not a fictitious signoff.
review_root = ROOT / "process-reviews"
review_root.mkdir(exist_ok=True)
for row in rows:
    target = review_root / f"{row['id']}.md"
    if target.exists():
        continue  # Never overwrite reviewer edits on regeneration.
    draft = (ROOT / row["document"]).read_text(encoding="utf-8")
    text = (
        f"# {row['id']} {row['project_activity']} 产物评审稿\n\n"
        f"过程组为{row['group']}，版本 0.1，状态为待评审。\n\n"
        f"## 本过程输出候选\n\n{row['proposed_output']}。"
        "本文件保留当前项目草案，逐项正式输出及更新项待教材正文核验。\n\n"
        "## 当前工作内容\n\n" + draft + "\n\n## 负责人评审\n\n"
        "| 输出或段落 | 意见 | 修改结果 | 复审决定 |\n"
        "|---|---|---|---|\n| 待填写 | 待审阅 | 未修改 | 未批准 |\n\n"
        "## 后续更新\n\n发生实际执行、测量和接受时补证据编号，批准后保存独立版本。\n"
    )
    target.write_text(text, encoding="utf-8")
