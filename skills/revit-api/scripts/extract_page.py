"""
extract_page.py - 从 RevitAPI 预提取的 JSON 数据中获取格式化 Markdown

用法:
    python extract_page.py --type "Autodesk.Revit.DB.Wall"          # 通过类型全名
    python extract_page.py --id "T:Autodesk.Revit.DB.Wall"          # 通过 Help ID
    python extract_page.py --id "P:Autodesk.Revit.DB.Wall.Flipped"  # 成员级别
"""

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
INDEX_PATH = SKILL_DIR / "data" / "api_index.json"
PAGES_DIR = SKILL_DIR / "data" / "pages"
LOOKUP_PATH = PAGES_DIR / "_lookup.json"


def load_lookup():
    """加载 help_id → namespace 查找表"""
    if not LOOKUP_PATH.exists():
        return {}
    with open(LOOKUP_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_page(ns: str, help_id: str) -> dict | None:
    """从命名空间 JSON 文件加载单个页面"""
    safe_name = ns.replace("::", ".") if ns else "_orphan"
    ns_path = PAGES_DIR / f"{safe_name}.json"
    if not ns_path.exists():
        return None
    with open(ns_path, "r", encoding="utf-8") as f:
        pages = json.load(f)
    return pages.get(help_id)


def format_page(data: dict) -> str:
    """将 JSON 页面数据格式化为 Markdown"""
    lines = []

    # 标题
    lines.append(f"# {data.get('title', 'Unknown')}")
    lines.append("")

    # 描述
    desc = data.get("desc", "")
    if desc:
        lines.append(f"> {desc}")
        lines.append("")

    # 命名空间
    ns = data.get("ns", "")
    if ns:
        lines.append(f"**Namespace**: `{ns}`")
        lines.append(f"**Assembly**: RevitAPI.dll")
        lines.append("")

    # C# 签名
    sig = data.get("sig", "")
    if sig:
        lines.append("## Syntax")
        lines.append("")
        lines.append("```csharp")
        lines.append(sig)
        lines.append("```")
        lines.append("")

    # 继承层次
    inherit = data.get("inherit", [])
    if inherit:
        lines.append("## Inheritance Hierarchy")
        lines.append("")
        for i, item in enumerate(inherit):
            indent = "  " * i
            lines.append(f"{indent}- {item}")
        lines.append("")

    # 成员表
    member_labels = {
        "props": "Properties",
        "methods": "Methods",
        "events": "Events",
        "fields": "Fields",
    }
    members = data.get("members", {})
    for key, label in member_labels.items():
        items = members.get(key, [])
        if not items:
            continue
        lines.append(f"## {label}")
        lines.append("")
        lines.append("| Name | Description |")
        lines.append("|------|-------------|")
        for m in items:
            name = m.get("n", "")
            mdesc = m.get("d", "").replace("\n", " ")
            lines.append(f"| `{name}` | {mdesc} |")
        lines.append("")

    # Remarks
    remarks = data.get("remarks", "")
    if remarks:
        lines.append("## Remarks")
        lines.append("")
        lines.append(remarks)
        lines.append("")

    return "\n".join(lines)


def resolve_type_to_help_id(type_name: str) -> str | None:
    """通过 api_index.json 将类型名转为 Help ID"""
    if not INDEX_PATH.exists():
        return None
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        index = json.load(f)

    # 精确匹配
    if type_name in index["types"]:
        return f"T:{type_name}"

    # 不区分大小写
    tn_lower = type_name.lower()
    for fqn, info in index["types"].items():
        if fqn.lower() == tn_lower:
            return f"T:{fqn}"
        if info["name"].lower() == tn_lower:
            return f"T:{fqn}"

    # 尝试直接在 lookup 中查找各种前缀
    lookup = load_lookup()
    for prefix in ("T:", "N:", "P:", "M:", "E:", "F:"):
        candidate = f"{prefix}{type_name}"
        if candidate in lookup:
            return candidate

    return None


def main():
    parser = argparse.ArgumentParser(description="从预提取 JSON 获取 API 文档")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--type", type=str, help="类型全名 (如 Autodesk.Revit.DB.Wall)")
    group.add_argument("--id", type=str, help="Help ID (如 T:Autodesk.Revit.DB.Wall)")
    args = parser.parse_args()

    lookup = load_lookup()

    if args.type:
        help_id = resolve_type_to_help_id(args.type)
        if not help_id:
            print(f"错误: 未找到类型 \"{args.type}\"")
            sys.exit(1)
    else:
        help_id = args.id

    ns = lookup.get(help_id)
    if not ns:
        print(f"错误: Help ID \"{help_id}\" 未在查找表中")
        print("可用前缀: T:(类型) P:(属性) M:(方法) E:(事件) F:(字段) N:(命名空间)")
        sys.exit(1)

    data = load_page(ns, help_id)
    if not data:
        print(f"错误: 未找到页面数据 (ns={ns}, id={help_id})")
        sys.exit(1)

    print(format_page(data))


if __name__ == "__main__":
    main()
