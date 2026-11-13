import hashlib
import tempfile
from pathlib import Path
import requests
import streamlit as st
from activity import activity_table
from engine import Index, ask
from ingest import parse, markdown
from sandbox import run_python

st.set_page_config(page_title="文档证据台", page_icon="📚", layout="centered")
s = st.session_state


@st.cache_data(ttl=45, show_spinner=False)
def available_models():
    with requests.Session() as session:
        session.trust_env = False
        try:
            r = session.get("http://127.0.0.1:11434/api/tags", timeout=2, allow_redirects=False)
            r.raise_for_status()
            names = [m["name"] for m in r.json()["models"] if "embed" not in m["name"].lower()]
            return sorted(names, key=lambda n: (n != "qwen3:30b-a3b", n))
        except (requests.RequestException, KeyError, ValueError):
            return []


def use_index(units, embed, signature, notes):
    index = Index(units, embed)
    s.update(idx=index, history=[], records=[], tool="", signature=signature, notes=notes)


st.title("文档证据台")
st.write("上传资料后直接提问。活动表可以按月计数，每个答案都能展开核对来源。")
with st.sidebar:
    st.header("问答设置")
    names = available_models()
    model = st.selectbox(
        "回答方式", names + ["仅查原文"], help="统计问题直接核算全表。其他问题交给所选本地模型。"
    )
    if not names:
        st.info("未连接到可用的 Ollama 问答模型。仍可统计活动或检索原文。")
    if st.button("重新检测模型"):
        available_models.clear()
        st.rerun()
    with st.expander("高级设置"):
        emb = st.text_input(
            "向量模型", help="默认使用本地字符向量。填写已安装的嵌入模型可启用语义检索。"
        )
        budget = st.slider("上下文预算", 2048, 16384, 4096, 512)
st.subheader("我的资料")
uploads = st.file_uploader(
    "拖入文件或点击选择，系统会自动解析",
    type=["pdf", "docx", "xlsx", "csv", "txt", "md"],
    accept_multiple_files=True,
)
if uploads:
    sig = (tuple((f.name, hashlib.sha256(f.getbuffer()).hexdigest()) for f in uploads), emb)
    if sig != s.get("signature"):
        try:
            with st.spinner("正在解析文件并建立索引…"):
                if len(uploads) > 20 or sum(f.size for f in uploads) > 100 * 1024**2:
                    raise ValueError("请将文件控制在 20 个、合计 100 MiB 以内")
                if len({f.name.casefold() for f in uploads}) != len(uploads):
                    raise ValueError("请先重命名同名文件，以便区分来源")
                units, notes = [], []
                with tempfile.TemporaryDirectory() as tmp:
                    for f in uploads:
                        path = Path(tmp) / Path(f.name).name
                        path.write_bytes(f.getbuffer())
                        rows, warnings = parse(path)
                        units.extend(rows)
                        notes.extend(f"{path.name} · {msg}" for msg in warnings)
                use_index(units, emb, sig, notes)
        except Exception as e:
            st.error(f"这批文件未完成解析：{e}")
            st.stop()
elif s.get("signature") != "demo":
    for key in ["idx", "signature", "records", "history", "tool", "notes"]:
        s.pop(key, None)
if not uploads and st.button("试用示例文档", help="使用内置的两页技术参数表体验引用"):
    rows, notes = parse(Path(__file__).parent / "examples/spec.pdf")
    use_index(rows, "", "demo", notes)
if "idx" not in s:
    st.info("可以上传活动表问“7月有多少活动”，也可以打开示例查一个具体参数。")
    st.stop()

idx = s.idx
docs = list(dict.fromkeys(u.file for u in idx.units))
st.success("可提问 · " + "、".join(docs))
for msg in s.get("notes", []):
    st.warning(msg)
with st.sidebar.expander("文档与计算工具"):
    st.download_button("导出解析文本", markdown(idx.units), "parsed.md")
    code = st.text_area("Python 计算（需要 Docker）", "print(18 * 1.13)")
    if st.button("执行并附到下个问题"):
        s.tool = ""
        try:
            s.tool = run_python(code)
        except Exception as e:
            st.error(str(e))
    if s.tool:
        st.code(s.tool)
st.subheader("向资料提问")
examples = (
    ["一共多少活动", "7月有多少活动"]
    if activity_table(idx.units)
    else (["BETA 的 pressure 是多少？"] if docs == ["spec.pdf"] else [])
)
preset = None
if examples:
    for col, label in zip(st.columns(len(examples)), examples):
        if col.button(label, use_container_width=True):
            preset = label
for q, a, refs, ledger in s.records:
    st.chat_message("user").write(q)
    with st.chat_message("assistant"):
        st.markdown(a)
        if refs:
            st.caption("引用来源 · " + "、".join(dict.fromkeys(u.file for u in refs)))
            with st.expander("核对来源与明细"):
                for n, u in enumerate(refs, 1):
                    st.markdown(f"**[S{n}]** {u.file} · {u.loc}")
                    st.text(u.text)
        if "total" in ledger:
            with st.expander("上下文用量"):
                st.json(ledger)
prompt = st.chat_input("输入问题，例如：7月有多少活动？")
if q := preset or prompt:
    try:
        with st.spinner("正在核对资料…"):
            a, refs, ledger = ask(
                idx, q, s.history, "" if model == "仅查原文" else model, budget, s.tool
            )
            if a.startswith("证据预览（未调用模型）"):
                a = f"找到 {len(refs)} 条相关原文，可展开来源逐条查看。需要综合回答时，请在侧栏选择问答模型。"
            s.records.append((q, a, refs, ledger))
            s.history.append((q, a))
            s.tool = ""
        st.rerun()
    except Exception as e:
        st.error(f"本次提问未完成：{e}")
