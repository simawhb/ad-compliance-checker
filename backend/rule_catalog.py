"""Obsidian 广告规则库的只读目录加载器。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_FRONTEND_INDUSTRY = {
    "cosmetic": "医疗健康",
    "medical": "医疗健康",
    "ecommerce": "电商促销",
    "education": "教育培训",
}
_FRONTEND_MEDIUM = {
    "taobao": "详情页",
    "pinduoduo": "详情页",
    "douyin": "短视频",
    "xiaohongshu": "短视频",
}


@dataclass(frozen=True)
class RuleSummary:
    rule_id: str
    status: str
    industry: tuple[str, ...]
    medium: tuple[str, ...]
    path: Path


def load_rule_catalog(rules_dir: str | Path) -> list[RuleSummary]:
    """读取规则 Markdown 的 YAML 前置信息，不读取客户材料或调用模型。"""
    root = Path(rules_dir)
    if not root.is_dir():
        raise ValueError(f"规则目录不存在: {root}")

    rules = [
        rule
        for path in sorted(root.glob("*.md"))
        if not path.name.startswith("._")
        if path.name != "规则条目模板.md"
        if (rule := _parse_rule(path)) is not None
    ]
    return rules


def select_rules(
    rules: Iterable[RuleSummary], industry: str, medium: str
) -> list[RuleSummary]:
    """按行业和媒介返回通用规则及匹配规则，供后续审查流程调用。"""
    matched = [
        rule
        for rule in rules
        if ("通用" in rule.industry or industry in rule.industry)
        and (not medium or not rule.medium or medium in rule.medium)
    ]
    return sorted(
        matched,
        key=lambda rule: (
            industry not in rule.industry,
            rule.rule_id,
        ),
    )


def select_frontend_rules(
    rules: Iterable[RuleSummary], industry_code: str, platform_code: str
) -> list[RuleSummary]:
    """把现有网页端枚举映射为规则库分类；食品等未细分品类只调用通用规则。"""
    return select_rules(
        rules,
        industry=_FRONTEND_INDUSTRY.get(industry_code, "通用"),
        medium=_FRONTEND_MEDIUM.get(platform_code, ""),
    )


def build_rule_context(rules: Iterable[RuleSummary], max_rules: int = 8) -> str:
    """生成有长度上限的已核验规则摘要，供模型审查时引用。"""
    excerpts: list[str] = []
    for rule in rules:
        if rule.status != "已核验":
            continue
        conclusion = _rule_conclusion(rule.path)
        if conclusion:
            excerpts.append(f"- [{rule.rule_id}] {conclusion[:240]}")
        if len(excerpts) >= max_rules:
            break
    return "\n".join(excerpts)


def rule_ids_in_context(context: str) -> set[str]:
    """返回实际写入模型提示词的规则编号。"""
    return {
        line[3 : line.find("]")]
        for line in context.splitlines()
        if line.startswith("- [") and "]" in line
    }


def _parse_rule(path: Path) -> RuleSummary | None:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None

    end = text.find("\n---", 4)
    if end == -1:
        return None

    fields = _parse_frontmatter(text[4:end])
    rule_id = fields.get("rule_id", "")
    if not rule_id:
        return None

    return RuleSummary(
        rule_id=rule_id,
        status=fields.get("status", ""),
        industry=_as_values(fields.get("industry", "")),
        medium=_as_values(fields.get("medium", "")),
        path=path,
    )


def _parse_frontmatter(frontmatter: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    active_list_key = ""
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if active_list_key and stripped.startswith("- "):
            existing = fields.get(active_list_key, "")
            fields[active_list_key] = ",".join(
                value for value in (existing, stripped[2:].strip()) if value
            )
            continue

        key, separator, value = line.partition(":")
        if separator:
            active_list_key = key.strip() if not value.strip() else ""
            fields[key.strip()] = value.strip()
        else:
            active_list_key = ""
    return fields


def _as_values(value: str) -> tuple[str, ...]:
    value = value.strip().strip("[]")
    if not value:
        return ()
    return tuple(item.strip().strip('"\'') for item in value.split(",") if item.strip())


def _rule_conclusion(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    marker = "## 规则结论"
    start = text.find(marker)
    if start == -1:
        return ""
    body = text[start + len(marker) :]
    next_section = body.find("\n## ")
    if next_section != -1:
        body = body[:next_section]
    return " ".join(line.strip() for line in body.splitlines() if line.strip())
