"""Generate synthetic fixtures and evaluate known row/locator pairs; no customer data."""

import argparse
import json
import time
from pathlib import Path

import pymupdf
from docx import Document
from openpyxl import Workbook
from engine import Index, prepare
from ingest import parse

ROOT = Path(__file__).resolve().parent / "examples"
CASES = [
    ("ALPHA pressure", "spec.pdf", "第 1 页", "17 kPa"),
    ("BETA pressure", "spec.pdf", "第 2 页", "71 kPa"),
    ("GAMMA voltage", "spec.pdf", "第 2 页", "48 V"),
    ("验收偏差", "contract.docx", "表行 2", "0.8 mm"),
    ("冷链保温时限", "delivery.xlsx", "A2:C2", "36 小时"),
    ("维修响应时限", "support.csv", "记录 2", "4 小时"),
]


def draw_grid(page, y, rows):
    xs = [45, 225, 380, 550]
    height = 29
    for x in xs:
        page.draw_line((x, y), (x, y + height * len(rows)))
    for i in range(len(rows) + 1):
        page.draw_line((xs[0], y + i * height), (xs[-1], y + i * height))
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            page.insert_text((xs[j] + 7, y + height * i + 19), val)


def fixtures(root=ROOT):
    root.mkdir(exist_ok=True, parents=True)
    doc = pymupdf.open()
    head = ["Item", "Metric", "Requirement"]
    p = doc.new_page()
    p.insert_text((45, 60), "Engineering specification - synthetic fixture")
    draw_grid(p, 695, [head, ["ALPHA", "pressure", "17 kPa"], ["ALPHA", "voltage", "24 V"]])
    p = doc.new_page()
    draw_grid(p, 48, [head, ["BETA", "pressure", "71 kPa"], ["GAMMA", "voltage", "48 V"]])
    doc.save(root / "spec.pdf")
    doc.close()
    word = Document()
    word.add_paragraph("示范合同，仅供回归测试。")
    tab = word.add_table(rows=2, cols=2)
    for row, vals in zip(tab.rows, [["项目", "允许偏差"], ["验收偏差", "0.8 mm"]]):
        for cell, v in zip(row.cells, vals):
            cell.text = v
    word.save(root / "contract.docx")
    book = Workbook()
    sheet = book.active
    sheet.title = "交付"
    for row in [
        ["对象", "项目", "上限"],
        ["运输", "冷链保温时限", "36 小时"],
        ["仓储", "常温周转", "60 小时"],
    ]:
        sheet.append(row)
    book.save(root / "delivery.xlsx")
    (root / "support.csv").write_text(
        "服务,时限\n维修响应时限,4 小时\n更换零件,48 小时\n", encoding="utf-8"
    )
    return [root / f for f in ("spec.pdf", "contract.docx", "delivery.xlsx", "support.csv")]


def evaluate(paths):
    units = [u for p in paths for u in parse(p)[0]]
    index = Index(units)
    result = []
    for q, file, loc, value in CASES:
        start = time.perf_counter()
        _, src, ledger = prepare(index, q, [], 2048)
        rank = next(
            (
                i
                for i, u in enumerate(src, 1)
                if u.file == file and loc in u.loc and value in u.text
            ),
            None,
        )
        result.append(
            dict(
                query=q,
                rank=rank,
                expected=value,
                latency_ms=round((time.perf_counter() - start) * 1000, 2),
                budget_used=ledger["total"],
            )
        )
    baselines = {}
    for mode in ("keyword", "vector", "hybrid"):
        hits = 0
        for q, file, loc, value in CASES:
            first = index.search(q, mode=mode)[:1]
            hits += any(u.file == file and loc in u.loc and value in u.text for u in first)
        baselines[mode] = hits / len(CASES)
    return {
        "dataset": "synthetic-v1",
        "questions": len(result),
        "units": len(units),
        "backend": "faiss" if index.faiss is not None else "numpy",
        "hit_at_1": sum(r["rank"] == 1 for r in result) / len(result),
        "hit_at_3": sum(0 < (r["rank"] or 999) <= 3 for r in result) / len(result),
        "retrieval_hit_at_1_by_mode": baselines,
        "cases": result,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--report", type=Path)
    args = p.parse_args()
    report = evaluate(fixtures())
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    print(text)
