"""
search_api.py - 搜索 RevitAPI 索引

用法:
    python search_api.py search <keyword>           # 按关键词搜索类名和描述
    python search_api.py namespace <ns_name>        # 列出命名空间下所有类型
    python search_api.py class <full_name>          # 查看特定类的成员概览
    python search_api.py member <member_name>       # 按成员名搜索（跨所有类）
    python search_api.py namespaces                 # 列出所有命名空间
"""

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
INDEX_PATH = SKILL_DIR / "data" / "api_index.json"

MAX_RESULTS = 20


def find_type_candidates(index, keyword, limit=8):
    """按类型名/全限定名给出候选类型"""
    kw = keyword.lower().strip()
    if not kw:
        return []

    matches = []
    for fqn, info in index["types"].items():
        name = info.get("name", "")
        name_lower = name.lower()
        fqn_lower = fqn.lower()

        score = 0
        if kw == name_lower:
            score = 100
        elif kw == fqn_lower:
            score = 95
        elif kw in name_lower:
            score = 80
        elif kw in fqn_lower:
            score = 60

        if score:
            matches.append((score, fqn, info))

    matches.sort(key=lambda x: (-x[0], x[1]))
    return matches[:limit]


def load_index():
    if not INDEX_PATH.exists():
        print(f"错误: 索引文件不存在: {INDEX_PATH}")
        print("请先运行 build_index.py 构建索引")
        sys.exit(1)
    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def cmd_search(index, keyword):
    """按关键词搜索类名和描述"""
    kw = keyword.lower()
    results = []

    for fqn, info in index["types"].items():
        score = 0
        name_lower = info["name"].lower()
        desc_lower = info.get("description", "").lower()

        # 精确匹配类名
        if name_lower == kw:
            score = 100
        # 类名包含关键词
        elif kw in name_lower:
            score = 80
        # 全限定名包含
        elif kw in fqn.lower():
            score = 60
        # 描述包含
        elif kw in desc_lower:
            score = 40
        # 多词搜索：所有词都出现在名称或描述中
        elif " " in kw:
            words = kw.split()
            combined = name_lower + " " + desc_lower + " " + fqn.lower()
            if all(w in combined for w in words):
                score = 50

        if score > 0:
            results.append((score, fqn, info))

    results.sort(key=lambda x: (-x[0], x[1]))
    results = results[:MAX_RESULTS]

    if not results:
        print(f"未找到与 \"{keyword}\" 相关的类型")
        return

    print(f"## 搜索结果: \"{keyword}\" ({len(results)} 条)")
    print()
    print("| 类型 | 种类 | 命名空间 | 描述 |")
    print("|------|------|----------|------|")
    for _, fqn, info in results:
        desc = info.get("description", "")
        if len(desc) > 60:
            desc = desc[:57] + "..."
        print(f"| **{info['name']}** | {info['kind']} | {info['namespace']} | {desc} |")

    print()
    print("*使用 `class <全限定名>` 查看成员详情*")


def cmd_namespace(index, ns_name):
    """列出命名空间下所有类型"""
    # 模糊匹配命名空间
    matched_ns = None
    ns_lower = ns_name.lower()
    for ns in index["namespaces"]:
        if ns.lower() == ns_lower:
            matched_ns = ns
            break
        elif ns_lower in ns.lower():
            matched_ns = ns
            break

    if not matched_ns:
        print(f"未找到命名空间: \"{ns_name}\"")
        print("\n可用命名空间:")
        for ns in sorted(index["namespaces"].keys()):
            if ns_lower in ns.lower():
                print(f"  - {ns}")
        return

    ns_info = index["namespaces"][matched_ns]
    desc = ns_info.get("description", "")
    type_names = ns_info.get("types", [])

    print(f"## {matched_ns}")
    if desc:
        print(f"> {desc}")
    print(f"\n**类型数量**: {len(type_names)}")
    print()

    if type_names:
        print("| 类型 | 种类 | 描述 |")
        print("|------|------|------|")
        for tname in sorted(type_names):
            fqn = f"{matched_ns}.{tname}"
            tinfo = index["types"].get(fqn, {})
            kind = tinfo.get("kind", "")
            tdesc = tinfo.get("description", "")
            if len(tdesc) > 70:
                tdesc = tdesc[:67] + "..."
            print(f"| **{tname}** | {kind} | {tdesc} |")


def cmd_class(index, class_name):
    """查看特定类的成员概览"""
    # 查找类型
    info = None
    fqn = None

    # 精确匹配
    if class_name in index["types"]:
        fqn = class_name
        info = index["types"][class_name]
    else:
        # 模糊匹配
        cn_lower = class_name.lower()
        for key, val in index["types"].items():
            if key.lower() == cn_lower:
                fqn = key
                info = val
                break
            elif val["name"].lower() == cn_lower:
                fqn = key
                info = val
                break

    if not info:
        print(f"未找到类型: \"{class_name}\"")
        # 建议搜索
        print(f"尝试: python search_api.py search \"{class_name}\"")
        return

    print(f"## {fqn}")
    print()
    if info.get("description"):
        print(f"> {info['description']}")
        print()
    print(f"- **种类**: {info['kind']}")
    print(f"- **命名空间**: {info['namespace']}")
    if info.get("signature"):
        print(f"- **签名**: `{info['signature']}`")
    print(f"- **文件**: `{info['file']}`")
    print()

    members = info.get("members", {})

    # Properties
    props = members.get("properties", [])
    if props:
        print(f"### Properties ({len(props)})")
        print()
        print("| 名称 | 描述 |")
        print("|------|------|")
        for p in props:
            desc = p["desc"]
            if len(desc) > 80:
                desc = desc[:77] + "..."
            print(f"| `{p['name']}` | {desc} |")
        print()

    # Methods
    methods = members.get("methods", [])
    if methods:
        print(f"### Methods ({len(methods)})")
        print()
        print("| 名称 | 描述 |")
        print("|------|------|")
        for m in methods:
            desc = m["desc"]
            if len(desc) > 80:
                desc = desc[:77] + "..."
            print(f"| `{m['name']}` | {desc} |")
        print()

    # Events
    events = members.get("events", [])
    if events:
        print(f"### Events ({len(events)})")
        print()
        print("| 名称 | 描述 |")
        print("|------|------|")
        for e in events:
            desc = e["desc"]
            if len(desc) > 80:
                desc = desc[:77] + "..."
            print(f"| `{e['name']}` | {desc} |")
        print()

    print(f"*使用 `extract_page.py --type \"{fqn}\"` 获取完整文档*")


def cmd_member(index, member_name):
    """按成员名搜索（跨所有类）"""
    mn_lower = member_name.lower()
    results = []

    for fqn, info in index["types"].items():
        members = info.get("members", {})
        for category in ("properties", "methods", "events"):
            for m in members.get(category, []):
                if mn_lower in m["name"].lower():
                    results.append({
                        "type": fqn,
                        "type_name": info["name"],
                        "category": category,
                        "name": m["name"],
                        "desc": m["desc"],
                    })

    if not results:
        print(f"未找到成员: \"{member_name}\"")
        candidates = find_type_candidates(index, member_name)
        if candidates:
            print("\n你输入的内容更像是类型名，可能要用以下命令：")
            for _, fqn, _ in candidates[:5]:
                print(f"  - python search_api.py class \"{fqn}\"")
            print("\n或：")
            print(f"  - python search_api.py search \"{member_name}\"")
        return

    results = results[:MAX_RESULTS]
    print(f"## 成员搜索: \"{member_name}\" ({len(results)} 条)")
    print()
    print("| 成员 | 类别 | 所属类型 | 描述 |")
    print("|------|------|----------|------|")
    for r in results:
        desc = r["desc"]
        if len(desc) > 50:
            desc = desc[:47] + "..."
        print(f"| `{r['name']}` | {r['category']} | {r['type_name']} | {desc} |")


def cmd_namespaces(index):
    """列出所有命名空间"""
    print(f"## 所有命名空间 ({len(index['namespaces'])})")
    print()
    print("| 命名空间 | 类型数 | 描述 |")
    print("|----------|--------|------|")
    for ns_name in sorted(index["namespaces"].keys()):
        ns = index["namespaces"][ns_name]
        count = len(ns.get("types", []))
        desc = ns.get("description", "")
        if len(desc) > 60:
            desc = desc[:57] + "..."
        print(f"| **{ns_name}** | {count} | {desc} |")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    index = load_index()

    if cmd == "search" and len(sys.argv) >= 3:
        cmd_search(index, " ".join(sys.argv[2:]))
    elif cmd == "namespace" and len(sys.argv) >= 3:
        cmd_namespace(index, " ".join(sys.argv[2:]))
    elif cmd == "class" and len(sys.argv) >= 3:
        cmd_class(index, " ".join(sys.argv[2:]))
    elif cmd == "member" and len(sys.argv) >= 3:
        cmd_member(index, " ".join(sys.argv[2:]))
    elif cmd == "namespaces":
        cmd_namespaces(index)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
