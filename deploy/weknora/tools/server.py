"""Pure evidence-processing tools. Input is supplied by an authorized WeKnora session."""

from decimal import Decimal, InvalidOperation
import os
from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
import httpx

mcp = FastMCP("企业文档核对", host="0.0.0.0", port=8710, stateless_http=True, json_response=True)


class Passage(BaseModel):
    source: str = Field(min_length=1, max_length=320)
    text: str = Field(min_length=1, max_length=8000)


@mcp.tool()
def pack_evidence(
    passages: Annotated[list[Passage], Field(min_length=1, max_length=20)],
    byte_budget: Annotated[int, Field(ge=256, le=16000)] = 4000,
) -> dict:
    """Pack already ranked search_knowledge results. Keep whole rows and original source IDs. Budget counts UTF-8 evidence bytes."""
    used = 0
    seen = set()
    selected = []
    for item in passages:
        identity = (item.source, " ".join(item.text.split()))
        if identity in seen:
            continue
        seen.add(identity)
        line = f"[{item.source}]\n{item.text}\n"
        size = len(line.encode("utf-8"))
        if used + size <= byte_budget:
            selected.append(line)
            used += size
    return {
        "evidence": "".join(selected),
        "input_count": len(passages),
        "selected_count": len(selected),
        "used_bytes": used,
        "budget_bytes": byte_budget,
    }


@mcp.tool()
def check_threshold(
    required: str,
    measured: str,
    required_unit: str,
    measured_unit: str,
    relation: Literal["minimum", "maximum", "exact"],
    requirement_source: str,
    measurement_source: str,
) -> dict:
    """Compare two document values; supply exact source locators from retrieval and matching units."""
    if not all(x.strip() for x in (requirement_source, measurement_source, required_unit)):
        raise ValueError("需要两个来源和单位")
    if measured_unit.strip() != required_unit.strip():
        raise ValueError("单位不同，请核实原文和换算关系")
    try:
        low, actual = Decimal(required), Decimal(measured)
        if not all(n.is_finite() for n in (low, actual)):
            raise ValueError("必须为有限数值")
    except InvalidOperation as exc:
        raise ValueError("请传入原始十进制数值") from exc
    passed = {"minimum": actual >= low, "maximum": actual <= low, "exact": actual == low}[relation]
    return dict(
        passed=passed,
        required=required,
        measured=measured,
        unit=required_unit,
        relation=relation,
        requirement_source=requirement_source,
        measurement_source=measurement_source,
    )


@mcp.tool()
def execute_python(code: Annotated[str, Field(min_length=1, max_length=8000)]) -> dict:
    """Execute Python for calculations on supplied authorized data in a disposable offline container.
    No host files or network. Limit 12 seconds, 128 MiB, 0.5 CPU, 32 processes, output 8 KiB.
    Print the result. Never assume knowledge-base rows are complete without reading the full table.
    """
    token = os.environ.get("RUNNER_TOKEN", "")
    if not token:
        raise ValueError("本地执行服务尚未配置")
    with httpx.Client(trust_env=False, timeout=35) as client:
        response = client.post(
            "http://host.docker.internal:18783/execute",
            headers={"Authorization": "Bearer " + token},
            json={"code": code},
        )
    if response.status_code != 200:
        raise ValueError("沙箱执行失败或达到限制")
    return response.json()


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
