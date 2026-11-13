"use strict";
const el = (id) => document.getElementById(id);
let token = sessionStorage.getItem("private-studio-token") || "";
let current = null,
  mode = "ask",
  redacted = null,
  restored = "",
  busy = false;
let libraryItems = [];
async function scopeDocuments() {
  el("document-scope").replaceChildren(
    new Option("所选知识库中的全部文档", ""),
  );
  if (!el("scope").value || el("scope").value === "__all__") return;
  const r = await data("/documents/" + encodeURIComponent(el("scope").value));
  for (const d of r.data || [])
    el("document-scope").add(new Option(d.title || d.file_name, d.id));
}
function notice(message, error = false) {
  el("notice").textContent = message;
  el("notice").classList.toggle("error", error);
  el("notice").hidden = !message;
}
async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = "Bearer " + token;
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.body);
  }
  const r = await fetch("/studio/api" + path, { ...options, headers });
  if (!r.ok) {
    let message;
    try {
      const data = await r.json();
      message =
        typeof data.detail === "string" ? data.detail : "输入格式不正确";
    } catch {
      message = "服务暂时不可用";
    }
    if (r.status === 401) {
      sessionStorage.removeItem("private-studio-token");
      token = "";
      showLogin();
    }
    throw Error(message);
  }
  return r;
}
async function data(path, options) {
  return (await api(path, options)).json();
}
async function persistEdits() {
  if(current && el("editor").value!==(current.body.edited_text??current.body.turns.at(-1).answer)){
    current=await data("/records/"+current.id,{method:"PUT",body:{revision:current.revision,text:el("editor").value}});
  }
}
async function run(action) {
  if (busy) return;
  busy = true;
  document.querySelectorAll("button").forEach((x) => (x.disabled = true));
  try {
    await action();
  } catch (e) {
    notice(e.message, true);
    if (!token)
      el("login-form").insertAdjacentText("beforeend", " " + e.message);
  } finally {
    busy = false;
    document.querySelectorAll("button").forEach((x) => (x.disabled = false));
  }
}
function download(content, name, type = "text/plain;charset=utf-8") {
  const url = URL.createObjectURL(
    content instanceof Blob ? content : new Blob([content], { type }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function page(id) {
  document.querySelectorAll(".page").forEach((x) => (x.hidden = x.id !== id));
  document
    .querySelectorAll(".nav")
    .forEach((x) => x.classList.toggle("active", x.dataset.page === id));
  el("page-label").textContent = {
    chat: "问答与创作",
    library: "我的知识库",
    privacy: "脱敏与还原",
  }[id];
  notice("");
}
function showLogin() {
  el("login").hidden = false;
  el("workspace").hidden = true;
}
async function enter() {
  const u = await data("/me");
  el("user-name").textContent = u.name;
  el("login").hidden = true;
  el("workspace").hidden = false;
  await libraries();
  await recent();
  page("chat");
}
async function libraries() {
  const result = await data("/libraries");
  libraryItems = result.libraries || [];
  for (const id of ["scope", "import-scope"]) {
    const old = el(id).value;
    el(id).replaceChildren(new Option("请选择知识库", ""));
    if (id === "scope" && libraryItems.length > 1)
      el(id).add(new Option("跨知识库 · 全部可访问资料", "__all__"));
    for (const item of libraryItems) el(id).add(new Option(item.name, item.id));
    if (libraryItems.some((x) => x.id === old)) el(id).value = old;
    else if (libraryItems.length === 1) el(id).value = libraryItems[0].id;
  }
  el("libraries-list").replaceChildren();
  for (const item of libraryItems) {
    const row = document.createElement("div");
    row.className = "book";
    const name = document.createElement("div");
    const title = document.createElement("h3");
    title.textContent = item.name;
    const desc = document.createElement("small");
    desc.textContent = item.description || "文档知识库";
    name.append(title, desc);
    const button = document.createElement("button");
    button.className = "secondary";
    button.textContent = "查看文档";
    button.onclick = () => run(() => loadDocuments(item.id));
    row.append(name, button);
    el("libraries-list").append(row);
  }
  if (!libraryItems.length) {
    const p = document.createElement("p");
    p.className = "empty";
    p.textContent = "还没有可用知识库。先创建一个课程或项目空间。";
    el("libraries-list").append(p);
  }
  if (!current) await scopeDocuments();
}
async function loadDocuments(kb) {
  const result = await data("/documents/" + encodeURIComponent(kb));
  const rows = result.data || [];
  el("documents-list").replaceChildren();
  for (const item of Array.isArray(rows) ? rows : rows.items || []) {
    const row = document.createElement("div");
    row.className = "book";
    const text = document.createElement("span");
    text.textContent = item.title || item.file_name || item.id;
    const state = document.createElement("small");
    state.textContent =
      "解析状态：" + (item.parse_status || item.status || "等待平台处理");
    row.append(text, state);
    el("documents-list").append(row);
  }
  if (!rows.length)
    el("documents-list").textContent = "暂未找到文档，请导入后等待索引完成。";
}
async function recent() {
  const result = await data("/records");
  el("recent").replaceChildren();
  for (const r of result.records) {
    const b = document.createElement("button");
    b.className = "recent";
    b.textContent = r.title;
    b.title = r.title;
    b.onclick = () =>
      run(async () => {
        current = await data("/records/" + r.id);
        render();
        page("chat");
      });
    el("recent").append(b);
  }
}
function render() {
  el("turns").replaceChildren();
  if (!current) {
    el("editor-panel").hidden = true;
    el("scope").disabled = false;
    el("document-scope").disabled = false;
    return;
  }
  el("scope").value =
    current.body.libraries.length > 1 ? "__all__" : current.body.libraries[0];
  el("scope").disabled = true;
  el("document-scope").disabled = true;
  if (current.body.documents?.length) {
    const id = current.body.documents[0];
    if (!Array.from(el("document-scope").options).some((x) => x.value === id))
      el("document-scope").add(new Option("本任务指定的文档", id));
    el("document-scope").value = id;
  } else el("document-scope").value = "";
  el("constraints").value = current.body.constraints || "";
  for (const turn of current.body.turns) {
    const article = document.createElement("article");
    article.className = "turn";
    const q = document.createElement("div");
    q.className = "question";
    q.textContent = turn.question;
    const a = document.createElement("div");
    a.className = "answer";
    a.textContent = turn.answer;
    article.append(q, a);
    for (const [i, s] of turn.sources.entries()) {
      const d = document.createElement("details");
      d.className = "source";
      const summary = document.createElement("summary");
      summary.textContent = "[S" + (i + 1) + "] " + s.file;
      const pre = document.createElement("pre");
      pre.textContent = s.selected_text || s.text;
      d.append(summary, pre);
      article.append(d);
    }
    const detail = document.createElement("details"),
      summary = document.createElement("summary"),
      pre = document.createElement("pre");
    summary.textContent = "上下文与引用检查";
    pre.textContent = JSON.stringify(turn.ledger, null, 2);
    detail.append(summary, pre);
    article.append(detail);
    el("turns").append(article);
  }
  const last = current.body.turns.at(-1);
  el("editor-panel").hidden = false;
  el("editor").value = current.body.edited_text ?? last.answer;
  el("task-hint").textContent = "正在继续同一任务，资料范围保持不变。";
}
document
  .querySelectorAll(".nav")
  .forEach((b) => (b.onclick = () => page(b.dataset.page)));
document.querySelectorAll(".mode").forEach(
  (b) =>
    (b.onclick = () => {
      mode = b.dataset.mode;
      document
        .querySelectorAll(".mode")
        .forEach((x) => x.classList.toggle("active", x === b));
      el("question").placeholder = {
        ask: "直接问一个知识或技术问题",
        review: "例如：整理这些资料中的核心概念、易错点和知识联系",
        quiz: "例如：围绕正则化出五道题，题目和解析分别呈现",
        outline: "例如：根据客户资料拟一份技术方案大纲，缺失信息列为待确认",
        write: "例如：根据所选资料和刚确认的大纲撰写方案初稿",
      }[mode];
    }),
);
el("new-chat").onclick = () =>
  run(async () => {
    await persistEdits();
    current = null;
    el("constraints").value = "";
    el("question").value = "";
    render();
    await scopeDocuments();
    page("chat");
  });
el("scope").onchange = () => run(scopeDocuments);
el("open-settings").onclick = () =>
  (el("settings").hidden = !el("settings").hidden);
el("compute").onclick = () =>
  run(async () => {
    const r = await data("/compute", {
      method: "POST",
      body: { code: el("compute-code").value },
    });
    el("compute-result").textContent = r.stdout;
  });
el("refresh").onclick = () => run(libraries);
el("setup-agent").onclick = () =>
  run(async () => {
    const r = await data("/setup-agent", { method: "POST" });
    notice(
      "本地工具已连接。请打开 WeKnora 平台，在智能体页选择「私有知识与复习助手」。",
    );
  });
el("load-demo").onclick = () =>
  run(async () => {
    notice("正在导入两门课程的自编演示资料…");
    const r = await data("/demo", { method: "POST" });
    await libraries();
    el("scope").value = r.library;
    el("import-scope").value = r.library;
    notice("演示资料已提交，索引完成后可问：结合高数和机器学习解释梯度下降。");
  });
el("refresh-docs").onclick = () =>
  run(async () => {
    await libraries();
    if (el("import-scope").value) await loadDocuments(el("import-scope").value);
  });
el("login-form").onsubmit = (e) => {
  e.preventDefault();
  run(async () => {
    const result = await data("/login", {
      method: "POST",
      body: { email: el("email").value, password: el("password").value },
    });
    el("password").value = "";
    token = result.token;
    sessionStorage.setItem("private-studio-token", token);
    await enter();
  });
};
el("logout").onclick = () => {
  token = "";
  sessionStorage.removeItem("private-studio-token");
  current = null;
  redacted = null;
  restored = "";
  location.reload();
};
el("library-form").onsubmit = (e) => {
  e.preventDefault();
  run(async () => {
    await data("/libraries", {
      method: "POST",
      body: {
        name: el("library-name").value,
        description: el("library-description").value,
      },
    });
    el("library-name").value = "";
    await libraries();
    notice("知识库已创建，可以导入资料。");
  });
};
el("import-form").onsubmit = (e) => {
  e.preventDefault();
  run(async () => {
    const file = el("upload").files[0];
    if (!file) throw Error("请选择资料");
    const form = new FormData();
    form.append("kb", el("import-scope").value);
    form.append("course", el("course").value);
    form.append("semester", el("semester").value);
    form.append("file", file);
    notice("正在还原文档结构并提交知识库…");
    const r = await data("/import", { method: "POST", body: form });
    notice(
      r.duplicate
        ? "这份相同资料已提交，无需重复入库。"
        : "资料已提交。后台索引可能需要一段时间，请刷新文档状态。",
    );
    await loadDocuments(el("import-scope").value);
  });
};
el("question-form").onsubmit = (e) => {
  e.preventDefault();
  run(async () => {
    if (!el("scope").value) throw Error("请先选择一个知识库");
    const question = el("question").value.trim();
    if (!question) throw Error("请输入问题");
    await persistEdits();
    notice("正在检索本地知识库并组织回答，请稍候…");
    const scope = current
      ? current.body.libraries
      : el("scope").value === "__all__"
        ? libraryItems.map((x) => x.id)
        : [el("scope").value];
    const documents = current
      ? current.body.documents || []
      : el("document-scope").value
        ? [el("document-scope").value]
        : [];
    current = await data("/ask", {
      method: "POST",
      body: {
        question,
        libraries: scope,
        documents,
        mode,
        constraints: el("constraints").value,
        budget: Number(el("budget").value),
        record_id: current?.id,
        revision: current?.revision,
      },
    });
    el("question").value = "";
    render();
    await recent();
    notice("已保存。可以追问，或在下方修改并导出成果。");
  });
};
el("save-edit").onclick = () =>
  run(async () => {
    current = await data("/records/" + current.id, {
      method: "PUT",
      body: { revision: current.revision, text: el("editor").value },
    });
    notice("修改已保存。");
  });
for (const [id, format] of [
  ["download-md", "md"],
  ["download-docx", "docx"],
]) {
  el(id).onclick = () =>
    run(async () => {
      if (
        el("editor").value !==
        (current.body.edited_text ?? current.body.turns.at(-1).answer)
      ) {
        current = await data("/records/" + current.id, {
          method: "PUT",
          body: { revision: current.revision, text: el("editor").value },
        });
      }
      const r = await api(
        "/records/" + current.id + "/export?format=" + format,
      );
      download(await r.blob(), "knowledge-document." + format);
    });
}
el("to-redact").onclick = () => {
  el("redact-view").hidden = false;
  el("restore-view").hidden = true;
};
el("to-restore").onclick = () => {
  el("redact-view").hidden = true;
  el("restore-view").hidden = false;
};
el("detect").onclick = () =>
  run(async () => {
    const r = await data("/privacy/detect", {
      method: "POST",
      body: { text: el("private-text").value },
    });
    const values = [
      ...new Set([
        ...el("private-values").value.split("\n").filter(Boolean),
        ...r.found.map((x) => x.value),
      ]),
    ];
    el("private-values").value = values.join("\n");
    invalidate();
    el("detected").textContent =
      "找到 " +
      r.found.length +
      " 个规则候选。请手动补充公司名、人员和项目代号等信息。";
  });
el("suggest").onclick = () =>
  run(async () => {
    notice("本地模型正在识别人员、公司和项目名称，完成后请人工核对…");
    const r = await data("/privacy/suggest", {
      method: "POST",
      body: { text: el("private-text").value },
    });
    el("private-values").value = [
      ...new Set([
        ...el("private-values").value.split("\n").filter(Boolean),
        ...r.found.map((x) => x.value),
      ]),
    ].join("\n");
    el("detected").textContent =
      "本地模型补充了 " + r.found.length + " 个名称候选，请检查并修正。";
    invalidate();
    notice("名称候选已加入替换列表，仍需核对漏项和误识别。");
  });
function invalidate() {
  redacted = null;
  el("redacted-panel").hidden = true;
  el("confirm-export").checked = false;
}
for (const id of ["private-text", "private-values", "map-password"])
  el(id).oninput = invalidate;
el("redact-button").onclick = () =>
  run(async () => {
    redacted = await data("/privacy/redact", {
      method: "POST",
      body: {
        text: el("private-text").value,
        values: el("private-values").value.split("\n"),
        password: el("map-password").value,
      },
    });
    el("redacted-preview").textContent = redacted.text;
    el("redacted-panel").hidden = false;
    el("confirm-export").checked = false;
    notice(
      "已替换 " +
        redacted.replaced +
        " 个不同字段。请检查预览并分别保存副本和加密映射包。",
    );
  });
el("export-redacted").onclick = () => {
  if (!redacted || !el("confirm-export").checked) {
    notice("请先核对预览并勾选导出确认。", true);
    return;
  }
  download(redacted.text, "redacted-" + redacted.task + ".md");
};
el("export-mapping").onclick = () => {
  if (redacted)
    download(
      redacted.mapping_package,
      "mapping-" + redacted.task + ".json",
      "application/json",
    );
};
el("restore-button").onclick = () =>
  run(async () => {
    const file = el("mapping-file").files[0];
    if (!file) throw Error("请选择对应的加密映射包");
    if (file.size > 2000000) throw Error("映射包过大");
    const r = await data("/privacy/restore", {
      method: "POST",
      body: {
        text: el("restore-text").value,
        mapping_package: await file.text(),
        password: el("restore-password").value,
      },
    });
    el("restore-report").textContent = r.blocked
      ? "还原已阻止。存在未知或被修改的占位符，请核对文本和任务。"
      : r.missing.length
        ? "已还原已识别字段；原任务有 " +
          r.missing.length +
          " 个占位符未出现在返回文本中，请检查是否被删改。"
        : "占位符已全部识别并还原。";
    restored = r.text || "";
    el("restored-preview").textContent = restored;
    el("export-restored").hidden = r.blocked;
  });
el("export-restored").onclick = () =>
  download(restored, "restored-document.md");
el("version-button").onclick=()=>run(async()=>{
  const r=await data("/records/"+current.id+"/versions");el("version-list").replaceChildren();
  for(const v of r.versions){
    const detail=document.createElement("details"),title=document.createElement("summary"),pre=document.createElement("pre");
    title.textContent="版本 "+v.revision+" · "+v.created;pre.textContent=v.text;detail.append(title,pre);el("version-list").append(detail);
  }
});
for(const id of ["restore-text","restore-password","mapping-file"])el(id).addEventListener("change",()=>{
  restored="";el("restored-preview").textContent="";el("restore-report").textContent="";el("export-restored").hidden=true;
});
if (token) run(enter);
