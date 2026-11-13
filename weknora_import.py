"""Prepare source-addressed Markdown and optionally ingest it into local WeKnora."""
import argparse
import getpass
import os
from pathlib import Path
from urllib.parse import quote

import requests
from activity import activity_table, count_activities
from ingest import parse


def source_document(path):
    units, notes = parse(path)
    if not units:
        raise ValueError("没有可导入的文本")
    sections = [f"# {path.name}"]
    if activity_table(units):
        sections.append("## 全表统计（按活动记录行计算）")
        for q in ["一共多少活动", *(f"{i}月有多少活动" for i in range(1, 13))]:
            answer, _, _ = count_activities(units, q)
            sections.append(answer.splitlines()[0].split("[S1]")[0].strip())
    sections.extend(f"## {u.file} · {u.loc}\n\n{u.text}" for u in units)
    if notes:
        sections.append("## 解析提示\n" + "\n".join(notes))
    return "\n\n".join(sections)


def upload(path, text, kb, key):
    url = f"http://127.0.0.1:18780/api/v1/knowledge-bases/{quote(kb, safe='')}/knowledge/file"
    filename = f"{path.name}.md"
    with requests.Session() as session:
        session.trust_env = False
        response = session.post(url, headers={"X-API-Key": key},
            files={"file": (filename, text.encode(), "text/markdown")},
            data={"fileName": filename}, timeout=(5, 120), allow_redirects=False)
    if not 200 <= response.status_code < 300:
        raise RuntimeError(f"WeKnora 上传失败 HTTP {response.status_code}")
    return response.json()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--export", type=Path)
    mode.add_argument("--kb", help="本机 WeKnora 知识库 ID")
    args = parser.parse_args()
    content = source_document(args.file)
    if args.export:
        args.export.write_text(content, encoding="utf-8")
    else:
        result = upload(args.file, content, args.kb, os.environ.get("WEKNORA_API_KEY") or getpass.getpass("WeKnora API Key: "))
        print(result)
