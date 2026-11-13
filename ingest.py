"""Local parsers. Each retrieval unit retains an address in the source."""

import csv
import io
from dataclasses import dataclass
from pathlib import Path
import pymupdf as pdf
from docx import Document
from docx.table import Table
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from zipfile import ZipFile


@dataclass(frozen=True)
class Unit:
    file: str
    loc: str
    text: str
    group: str = ""


def cells(row):
    return [
        str(v if v is not None else "").strip().replace("\n", " ").replace("|", "\\|") for v in row
    ]


def table_rows(name, rows, location, group, header=None):
    if not rows:
        return []
    head = header or cells(rows[0])
    start = 0 if header else 1
    result = []
    for i in range(start, len(rows)):
        row = cells(rows[i])
        if not any(row):
            continue
        width = max(len(head), len(row))
        h = head + [""] * (width - len(head))
        r = row + [""] * (width - len(row))
        md = "\n".join("| " + " | ".join(vals) + " |" for vals in (h, ["---"] * width, r))
        result.append(Unit(name, location(i + 1), md, group))
    return result


def prose(name, loc, text):
    return [
        Unit(name, loc + (f" · 段 {i // 900 + 1}" if len(text) > 900 else ""), text[i : i + 900])
        for i in range(0, len(text), 900)
        if text[i : i + 900].strip()
    ]


def parse(path):
    path = Path(path)
    name = path.name
    ext = path.suffix.lower()
    if path.stat().st_size > 25 * 1024**2:
        raise ValueError("单个文件上限为 25 MiB")
    if ext in {".xlsx", ".docx", ".pptx"}:
        with ZipFile(path) as archive:
            if sum(i.file_size for i in archive.infolist()) > 100 * 1024**2:
                raise ValueError("Office 文档解压后超过 100 MiB")
    out = []
    warnings = []
    if ext == ".pdf":
        with pdf.open(path) as doc:
            if doc.needs_pass:
                raise ValueError("请先提供可读取的 PDF")
            if len(doc) > 300:
                raise ValueError("PDF 超出 300 页上限")
            prev = None
            for pi, page in enumerate(doc, 1):
                boxes = []
                next_prev = None
                tables = sorted(page.find_tables().tables, key=lambda t: t.bbox[1])
                for ti, t in enumerate(tables, 1):
                    rows = t.extract()
                    if not rows:
                        continue
                    box = pdf.Rect(t.bbox)
                    boxes.append(box)
                    head = cells(rows[0])
                    group = f"p{pi}-t{ti}"
                    # Conservative continuation: matching x boundaries and repeated header.
                    if (
                        prev
                        and ti == 1
                        and box.y0 < page.rect.height * 0.25
                        and prev[0] == head
                        and abs(prev[1] - box.x0) < 4
                        and abs(prev[2] - box.x1) < 4
                    ):
                        group = prev[3]
                    if box.y1 > page.rect.height * 0.72:
                        next_prev = (head, box.x0, box.x1, group)
                    out.extend(
                        table_rows(name, rows, lambda r: f"第 {pi} 页 · 表 {ti} 行 {r}", group)
                    )
                prev = next_prev
                blocks = page.get_text("blocks", sort=True)
                for b in blocks:
                    rect = pdf.Rect(b[:4])
                    if len(b) > 6 and b[6] != 0:
                        continue
                    if any((rect & box).get_area() > 0.6 * rect.get_area() for box in boxes):
                        continue
                    out.extend(prose(name, f"第 {pi} 页", b[4].strip()))
                if not page.get_text().strip():
                    warnings.append(f"第 {pi} 页无文本层，需 OCR")
    elif ext == ".docx":
        doc = Document(path)
        for i, item in enumerate(doc.iter_inner_content(), 1):
            if isinstance(item, Table):
                out.extend(
                    table_rows(
                        name,
                        [[c.text for c in row.cells] for row in item.rows],
                        lambda r: f"块 {i} · 表行 {r}",
                        f"t{i}",
                    )
                )
            else:
                out.extend(prose(name, f"段落块 {i}", item.text))
    elif ext == ".pptx":
        from pptx import Presentation
        deck = Presentation(path)
        if len(deck.slides) > 300:
            raise ValueError("课件超过 300 页上限")
        for pi, slide in enumerate(deck.slides, 1):
            for si, shape in enumerate(sorted(slide.shapes, key=lambda s:(s.top,s.left)), 1):
                if shape.has_table:
                    rows=[[c.text for c in row.cells] for row in shape.table.rows]
                    out.extend(table_rows(name,rows,lambda r:f"幻灯片 {pi} · 表 {si} 行 {r}",f"slide{pi}-t{si}"))
                elif shape.has_text_frame:
                    out.extend(prose(name,f"幻灯片 {pi} · 文本块 {si}",shape.text))
                elif shape.shape_type == 13:
                    warnings.append(f"幻灯片 {pi} 包含图片，图片内容尚未 OCR")
    elif ext == ".xlsx":
        wb = load_workbook(path, read_only=True, data_only=True)
        try:
            for ws in wb.worksheets:
                if (ws.max_row or 0) * (ws.max_column or 0) > 250000:
                    raise ValueError("单张工作表超过 25 万单元格")
                rows = list(ws.values)
                if rows:
                    out.extend(
                        table_rows(
                            name,
                            rows,
                            lambda r: f"{ws.title}!A{r}:{get_column_letter(len(rows[0]))}{r}",
                            ws.title,
                        )
                    )
        finally:
            wb.close()
    elif ext == ".csv":
        rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
        out = table_rows(name, rows, lambda r: f"记录 {r}", "csv")
    elif ext in {".md", ".txt"}:
        out = prose(name, "正文", path.read_text(encoding="utf-8-sig"))
    else:
        raise ValueError(f"不支持的格式 {ext}")
    return out, warnings


def markdown(units):
    parts = []
    last = None
    for u in units:
        key = (u.file, u.group)
        if u.group and last == key:
            parts.append(u.text.splitlines()[-1])
        else:
            parts.extend(["", f"### {u.file} · {u.loc}", "", u.text])
        last = key if u.group else None
    return "\n".join(parts)
