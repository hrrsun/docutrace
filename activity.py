"""Deterministic counts over all activity rows, independent of retrieval depth."""

import re
from collections import defaultdict
from ingest import Unit

NAME = {"活动名称", "活动名", "活动主题"}
TIME = {"时间", "日期", "活动日期", "活动时间", "举办时间"}
CN = "一 二 三 四 五 六 七 八 九 十 十一 十二".split()
MONTH = r"(?:1[0-2]|0?[1-9]|十一|十二|十|[一二三四五六七八九])"


def month_number(value):
    return int(value) if value.isdigit() else CN.index(value) + 1


def fields(unit):
    if not unit.group:
        return [], []
    lines = unit.text.splitlines()
    if len(lines) != 3:
        return [], []
    return [
        list(map(str.strip, re.split(r"(?<!\\)\|", line.strip("| "))))
        for line in (lines[0], lines[2])
    ]


def activity_table(units):
    return any(NAME.intersection(fields(u)[0]) for u in units)


def months(text):
    # One row can cover multiple months. Expand only explicit range separators.
    pattern = rf"(?:\d{{4}}年)?(?P<cn>{MONTH})月(?:\d{{1,2}}日)?|\b\d{{4}}[-/.](?P<iso>1[0-2]|0?[1-9])[-/.]\d{{1,2}}"
    matches = list(re.finditer(pattern, text))
    values = [month_number(m["cn"] or m["iso"]) for m in matches]
    found = set(values)
    for a, b, x, y in zip(matches, matches[1:], values, values[1:]):
        if re.fullmatch(r"\s*[-~～—至到]\s*", text[a.end() : b.start()]):
            found.update(range(x, y + 1) if y >= x else [*range(x, 13), *range(1, y + 1)])
    return found


def count_activities(units, question):
    q = re.sub(r"[\s？?。，！!]", "", question)
    match = re.fullmatch(
        rf"(?:请问|请统计)?(?:(?P<m>{MONTH})月份?)?(?:一共|共有|总共|总计|总数|有|共|合计|总共有)*"
        r"(?:多少|几)(?:个|项|场|次)?(?:志愿)?活动",
        q,
    )
    if not match and q not in {"活动总数", "活动数量", "统计活动总数", "活动一共有多少个"}:
        return None
    target = month_number(match["m"]) if match and match["m"] else None
    grouped = defaultdict(list)
    hits = unknown = 0
    for u in units:
        head, row = fields(u)
        col = next((i for i, v in enumerate(head) if v in NAME), None)
        if col is None:
            continue
        group = grouped[(u.file, u.group)]
        name = row[col] if col < len(row) else ""
        if name in NAME | {"合计", "总计", "小计", "待定", "暂无"} or not re.search(
            r"[\w\u3400-\u9fff]", name
        ):
            continue
        time_col = next((i for i, v in enumerate(head) if v in TIME), None)
        date = row[time_col] if time_col is not None and time_col < len(row) else ""
        mm = months(date)
        hit = target is None or target in mm
        unknown += int(target is not None and not mm)
        hits += int(hit)
        group.append((u.loc, date, name, hit))
    if not grouped:
        return None
    refs = []
    for (file, sheet), rows in grouped.items():
        audit = "\n".join(
            f"{'计入' if hit else '未计入'} · {loc} · {date} · {name}"
            for loc, date, name, hit in rows
        )
        refs.append(Unit(file, sheet, audit or "无有效活动记录"))
    total = sum(map(len, grouped.values()))
    label = f"{target}月" if target else "全表"
    answer = (
        f"{label}共 **{hits} 场活动**。"
        if not unknown
        else f"能确认属于{target}月的有 **{hits} 场**，另有 {unknown} 条日期无法判断。"
    )
    answer += " " + " ".join(f"[S{i + 1}]" for i in range(len(refs)))
    answer += f"\n\n已核对 {total} 条有效活动记录。每行计一场，跨月活动计入涉及的月份。"
    return (
        answer,
        refs,
        {"mode": "全表统计", "valid_rows": total, "matched_rows": hits, "unknown_dates": unknown},
    )
