# -*- coding: utf-8 -*-
"""
广告合规检测引擎 v2.1 — 力邦营养定制版
基于知识库的规则引擎，支持规则分层、风险分级、行业专项审查、具体替换建议
"""
import json
import os
import re
import time

# 指向共享知识库（与原版共用，未来可定制力邦营养专用版）
# KB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "ad-compliance-checker", "knowledge", "forbidden_words.json")
# 如果独立部署时需本地副本，复制上方文件到 knowledge/ 目录并取消注释下面一行
KB_PATH = os.path.join(os.path.dirname(__file__), "..", "knowledge", "forbidden_words.json")

_kb_cache = None
_kb_mtime = 0
_kb_loaded = False

def get_kb():
    global _kb_cache, _kb_mtime, _kb_loaded
    try:
        mtime = os.path.getmtime(KB_PATH)
        if not _kb_loaded or mtime != _kb_mtime:
            with open(KB_PATH, "r", encoding="utf-8") as f:
                _kb_cache = json.load(f)
            _kb_mtime = mtime
            _kb_loaded = True
    except Exception as e:
        if not _kb_loaded:
            raise RuntimeError(f"知识库加载失败: {e}")
    return _kb_cache

_compiled_forbidden = []
_compiled_allowed = []
_compiled_industry = {}
_compiled_platform = {}
_platform_tips = {}

def compile_kb():
    kb = get_kb()
    _compiled_forbidden.clear()
    _compiled_allowed.clear()
    _compiled_industry.clear()

    for cat_key, cat in kb.get("categories", {}).items():
        for item in cat.get("words", []):
            word = item if isinstance(item, str) else item.get("w", "")
            if not word:
                continue
            try:
                pattern = re.compile(re.escape(word), re.IGNORECASE)
                _compiled_forbidden.append((pattern, word, cat_key, cat))
            except Exception:
                continue

    allowed = kb.get("cosmetics_allowed", {})
    for word in allowed.get("words", []):
        try:
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            _compiled_allowed.append((pattern, word))
        except Exception:
            continue

    for ind_key, ind_data in kb.get("industry", {}).items():
        patterns = []
        for word in ind_data.get("extra", []):
            try:
                pattern = re.compile(re.escape(word), re.IGNORECASE)
                patterns.append((pattern, word))
            except Exception:
                continue
        _compiled_industry[ind_key] = patterns

    _compiled_platform.clear()
    _platform_tips.clear()
    for plat_key, plat_data in kb.get("platforms", {}).items():
        patterns = []
        for word in plat_data.get("words", []):
            try:
                pattern = re.compile(re.escape(word), re.IGNORECASE)
                patterns.append((pattern, word))
            except Exception:
                continue
        _compiled_platform[plat_key] = patterns
        _platform_tips[plat_key] = plat_data.get("tips", [])

_REPLACE_MAP = {
    "最佳": ("优质", "避免最高级表述"),
    "最好": ("优质", "避免最高级表述"),
    "最优": ("优良", "避免最高级表述"),
    "最强": ("强劲", "避免最高级表述"),
    "最新": ("新一代", "避免最高级表述"),
    "最先进": ("先进", "避免最高级表述"),
    "最低": ("较低", "避免最高级表述"),
    "最高": ("较高", "避免最高级表述"),
    "最大": ("较大", "避免最高级表述"),
    "最小": ("较小", "避免最高级表述"),
    "第一": ("领先", "避免序数表述，除非有数据支撑"),
    "唯一": ("专注", "避免排他性表述"),
    "顶级": ("高端", "避免最高级表述"),
    "极致": ("精工", "避免绝对化表述"),
    "极品": ("精品", "避免绝对化表述"),
    "国家级": ("行业认可", "避免国家级表述"),
    "最高级": ("高级", "避免最高级表述"),
    "史上最": ("多年来", "避免绝对化时间表述"),
    "全网最": ("网上", "避免最高级表述"),
    "全球首创": ("创新", "避免绝对化表述"),
    "行业领先": ("专业", "避免排名表述，除非有数据支撑"),
    "销量冠军": ("热销", "避免排名表述，除非有数据支撑"),
    "绝无仅有": ("稀缺", "避免绝对化表述"),
    "独一无二": ("独特", "避免绝对化表述"),
    "举世无双": ("卓越", "避免绝对化表述"),
    "无与伦比": ("出色", "避免绝对化表述"),
    "天下第一": ("领先", "避免排名表述"),
    "世界第一": ("全球领先", "避免排名表述，除非有数据支撑"),
    "全国第一": ("全国领先", "避免排名表述，除非有数据支撑"),
    "永久": ("长期", "避免永久性承诺"),
    "驰名商标": ("知名品牌", "驰名商标已禁止用于广告宣传"),
    "国家免检": ("质量可靠", "国家免检已取消"),
    "老字号": ("历史悠久", "需有官方认定才能使用"),
    "100%有效": ("效果显著", "避免绝对化效果承诺"),
    "100%安全": ("安全可靠", "避免绝对化安全承诺"),
    "包治百病": ("适用范围广", "避免虚假医疗承诺"),
    "药到病除": ("效果显著", "避免虚假医疗承诺"),
    "立竿见影": ("见效快", "避免绝对化效果承诺"),
    "立即见效": ("见效快", "避免绝对化效果承诺"),
    "永不反弹": ("效果持久", "避免绝对化承诺"),
    "彻底根治": ("有效改善", "避免虚假医疗承诺"),
    "彻底治愈": ("有效改善", "避免虚假医疗承诺"),
    "零风险": ("风险较低", "避免绝对化承诺"),
    "零副作用": ("副作用小", "避免绝对化承诺"),
    "无效退款": ("效果保障", "需有明确退款条件才能使用"),
    "纯天然": ("天然成分", "需有检测报告支撑"),
    "无任何副作用": ("副作用小", "避免绝对化承诺"),
    "不伤皮肤": ("温和配方", "避免绝对化承诺"),
    "治疗": ("辅助改善", "普通商品不得宣传治疗功效"),
    "治愈": ("辅助改善", "普通商品不得宣传治愈功效"),
    "根治": ("有效改善", "普通商品不得宣传根治功效"),
    "消炎": ("舒缓", "普通商品不得宣传消炎功效"),
    "杀菌": ("抑菌", "普通商品不得宣传杀菌功效"),
    "抗癌": ("健康", "普通商品绝对禁止宣传抗癌功效"),
    "防癌": ("健康", "普通商品绝对禁止宣传防癌功效"),
    "降血压": ("健康", "普通商品不得宣传降血压功效"),
    "降血糖": ("健康", "普通商品不得宣传降血糖功效"),
    "降血脂": ("健康", "普通商品不得宣传降血脂功效"),
    "减肥": ("体重管理", "普通商品不得宣传减肥功效"),
    "增强免疫力": ("健康", "普通商品不得宣传增强免疫力功效"),
    "提高免疫力": ("健康", "普通商品不得宣传提高免疫力功效"),
    "延缓衰老": ("健康", "普通商品不得宣传延缓衰老功效"),
    "抗衰老": ("健康", "普通商品不得宣传抗衰老功效"),
    "明目": ("护眼", "普通商品不得宣传明目功效"),
    "护肝": ("肝脏健康", "普通商品不得宣传护肝功效"),
    "补肾": ("肾脏健康", "普通商品不得宣传补肾功效"),
    "壮阳": ("男性健康", "普通商品不得宣传壮阳功效"),
    "止痛": ("舒缓", "普通商品不得宣传止痛功效"),
    "安眠": ("助眠", "普通商品不得宣传助眠功效"),
    "止咳": ("润喉", "普通商品不得宣传止咳功效"),
    "化痰": ("呼吸道健康", "普通商品不得宣传化痰功效"),
    "清热解毒": ("清热", "普通商品不得宣传清热解毒功效"),
    "活血化瘀": ("血液循环", "普通商品不得宣传活血化瘀功效"),
    "强身健体": ("健康", "普通商品不得宣传强身健体功效"),
    "美容养颜": ("美容", "普通商品不得宣传美容养颜功效"),
    "市场最低价": ("价格优惠", "需有真实价格对比数据"),
    "出厂价": ("优惠价", "需确保是真实出厂价"),
    "仅限一天": ("限时优惠", "需确保活动时间真实"),
    "最后一天": ("限时优惠", "需确保活动时间真实"),
    "原价": ("日常价", "需确保原价真实存在"),
    "保本": ("稳健", "金融产品不得承诺保本"),
    "稳赚": ("稳健", "金融产品不得使用稳赚表述"),
    "保过": ("辅导", "教育培训不得承诺保过"),
    "包过": ("辅导", "教育培训不得承诺包过"),
    "学区房": ("优质教育配套", "学区划分以教育局公布为准"),
    "投资回报": ("增值潜力", "房地产广告不得承诺投资回报"),
}

_CHEDI_REPLACE_MAP = {
    "痘痘": "祛痘", "色斑": "淡斑", "皱纹": "抗皱",
    "暗沉": "提亮", "毛孔": "收缩毛孔", "黑头": "去黑头",
    "粉刺": "去粉刺", "痤疮": "祛痘", "皮炎": "舒缓皮肤",
    "湿疹": "舒缓皮肤", "过敏": "舒缓皮肤", "敏感": "舒缓皮肤",
    "干燥": "保湿", "油腻": "控油", "粗糙": "细腻",
    "松弛": "紧致", "下垂": "提升", "黑眼圈": "淡化黑眼圈",
    "眼袋": "淡化眼袋", "法令纹": "淡化法令纹", "鱼尾纹": "淡化鱼尾纹",
    "抬头纹": "淡化抬头纹", "颈纹": "淡化颈纹",
    "妊娠纹": "淡化妊娠纹", "肥胖纹": "淡化肥胖纹", "生长纹": "淡化生长纹",
    "疤痕": "淡化疤痕", "痘印": "淡化痘印", "色素沉着": "淡化色素",
    "肤色不均": "均匀肤色", "暗黄": "提亮",
    "无光泽": "提亮", "无弹性": "增加弹性", "无活力": "增加活力",
    "无生机": "增加生机", "无光彩": "增加光彩", "无色泽": "增加色泽",
    "无血色": "增加血色", "无气色": "增加气色", "无精神": "增加精神",
}

_FILING_SUGGEST_MAP = {
    "美白": "需确保已完成功效宣称备案",
    "防晒": "需确保已完成功效宣称备案",
    "祛斑": "需确保已完成功效宣称备案",
    "祛痘": "需确保已完成功效宣称备案",
    "抗皱": "需确保已完成功效宣称备案",
    "保湿": "需确保已完成功效宣称备案",
    "紧致": "需确保已完成功效宣称备案",
    "控油": "需确保已完成功效宣称备案",
    "去角质": "需确保已完成功效宣称备案",
    "舒缓": "需确保已完成功效宣称备案",
    "修护": "需确保已完成功效宣称备案",
    "滋养": "需确保已完成功效宣称备案",
    "防脱发": "需确保已完成功效宣称备案",
    "去屑": "需确保已完成功效宣称备案",
}

_FSMP_TIPS = {
    "fsmp": [
        "特殊医学用途配方食品必须经国家市场监管总局注册，取得国食注字注册号",
        "广告不得涉及疾病预防、治疗功能，不得使用医疗用语",
        "标签必须标注适用人群、食用方法、警示说明",
        "0-12月龄产品不得进行广告宣传",
        "营养食品不得暗示可替代正常饮食或母乳",
        "需在医生或临床营养师指导下使用的警示说明必须标注",
    ],
    "food": [
        "食品广告不得涉及疾病预防、治疗功能宣称",
        "不得使用医疗用语或暗示保健功效",
        "营养声称需符合GB 28050规定",
        "特殊膳食食品需标注适宜人群和不适宜人群",
    ],
    "general": [
        "建议保留证据材料，包括检测报告、专利证书等",
        "数据引证需标明出处和时间范围",
    ],
}


def _match_chedi_patterns(text):
    risks = []
    for match in re.finditer(r"彻底解决\S{2,6}", text):
        full_word = match.group()
        idx = match.start()
        suffix = full_word[4:]
        if suffix in _CHEDI_REPLACE_MAP:
            replace_to = _CHEDI_REPLACE_MAP[suffix]
            risks.append({
                "word": full_word,
                "category": "化妆品违规词",
                "severity": "high",
                "risk_level": "high",
                "rule_layer": "A",
                "law": "广告法第十七条/化妆品监督管理条例",
                "suggest": f"将\"{full_word}\"改为\"{replace_to}\"，化妆品不得使用夸大表述",
                "replace_to": replace_to,
                "reason": "化妆品不得使用夸大表述",
                "position": idx,
                "type": "forbidden",
                "needs_evidence": False,
            })
    return risks


# 行业 => 排除的类别映射（避免行业不相关的类别干扰检测结果）
_INDUSTRY_EXCLUDE_CATEGORIES = {
    "fsmp": {"cosmetics", "medical_beauty"},
    "food": {"cosmetics", "medical_beauty"},
    "cosmetic": set(),
    "medical": set(),
    "education": set(),
    "finance": set(),
    "realestate": set(),
}


def detect(text, industry="", platform=""):
    kb = get_kb()
    risks = []

    # 根据行业排除不相关的类别（如检测特医食品时排除化妆品类别）
    exclude = _INDUSTRY_EXCLUDE_CATEGORIES.get(industry, set())
    risks.extend(_match_forbidden_words(text, exclude_categories=exclude))
    risks.extend(_match_chedi_patterns(text))
    risks.extend(_match_allowed_words(text, kb))

    if industry:
        risks.extend(_match_industry(text, industry))

    if platform:
        risks.extend(_match_platform(text, platform))

    risks = _deduplicate(risks)
    risks = _apply_absolute_exceptions(text, risks, kb)
    risks = _apply_replace_suggestions(risks)
    score = _calculate_score(risks)
    tips = _generate_tips(risks, kb, industry, platform)

    return {
        "score": score,
        "risk_count": len([r for r in risks if r["risk_level"] in ("critical", "high")]),
        "risks": risks,
        "summary": _generate_summary(risks),
        "compliance_tips": tips,
        "risk_distribution": _get_risk_distribution(risks)
    }


def _match_forbidden_words(text, exclude_categories=None):
    risks = []
    if not _compiled_forbidden:
        return risks
    for pattern, word, cat_key, cat in _compiled_forbidden:
        if exclude_categories and cat_key in exclude_categories:
            continue
        for match in pattern.finditer(text):
            severity = cat.get("severity", "high")
            risks.append({
                "word": word,
                "category": cat["name"],
                "severity": severity,
                "risk_level": _map_severity_to_risk_level(severity),
                "rule_layer": _get_rule_layer(cat_key),
                "law": cat.get("law", ""),
                "suggest": _get_default_suggest(cat_key),
                "reason": cat.get("note", cat["name"]),
                "position": match.start(),
                "type": "forbidden",
                "needs_evidence": False,
            })
    return risks


def _match_allowed_words(text, kb):
    risks = []
    if not _compiled_allowed:
        return risks
    for pattern, word in _compiled_allowed:
        for match in pattern.finditer(text):
            suggest = _FILING_SUGGEST_MAP.get(word, "需确保已完成功效宣称备案")
            risks.append({
                "word": word,
                "category": kb.get("cosmetics_allowed", {}).get("name", "化妆品合规功效词"),
                "severity": "info",
                "risk_level": "info",
                "rule_layer": "B",
                "law": kb.get("cosmetics_allowed", {}).get("regulation", ""),
                "suggest": suggest,
                "reason": "化妆品合规功效词，需备案后方可使用",
                "position": match.start(),
                "type": "allowed_with_filing",
                "needs_evidence": True,
            })
    return risks


def _match_platform(text, platform):
    risks = []
    patterns = _compiled_platform.get(platform, [])
    for pattern, word in patterns:
        for match in pattern.finditer(text):
            risks.append({
                "word": word,
                "category": "平台专项",
                "severity": "high",
                "risk_level": "high",
                "rule_layer": "C",
                "law": "平台规则",
                "suggest": '平台敏感词「' + word + '」，建议删除或替换',
                "reason": f"平台敏感词",
                "position": match.start(),
                "type": "forbidden",
                "needs_evidence": False,
            })
    return risks


def _match_industry(text, industry):
    risks = []
    patterns = _compiled_industry.get(industry, [])
    for pattern, word in patterns:
        for match in pattern.finditer(text):
            risks.append({
                "word": word,
                "category": "行业专项",
                "severity": "high",
                "risk_level": "high",
                "rule_layer": "C",
                "law": "行业规范",
                "suggest": "建议删除",
                "reason": "行业敏感词",
                "position": match.start(),
                "type": "industry",
                "needs_evidence": False,
            })
    return risks


def _deduplicate(risks):
    sev_order = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
    risks.sort(key=lambda r: (r["position"], -len(r["word"])))
    result = []
    for r in risks:
        r_start = r["position"]
        r_end = r_start + len(r["word"])
        r_sev = sev_order.get(r["risk_level"], 0)
        dominated = False
        for existing in result:
            e_start = existing["position"]
            e_end = e_start + len(existing["word"])
            e_sev = sev_order.get(existing["risk_level"], 0)
            if e_start <= r_start and r_end <= e_end and e_sev >= r_sev:
                dominated = True
                break
        if not dominated:
            result = [
                e for e in result
                if not (r_start <= e["position"]
                        and e["position"] + len(e["word"]) <= r_end
                        and r_sev > sev_order.get(e["risk_level"], 0))
            ]
            result.append(r)
    return result


def _apply_absolute_exceptions(text, risks, kb):
    if "absolute_terms_exceptions" not in kb:
        return risks
    absolute_words = set()
    if "absolute" in kb["categories"]:
        for w in kb["categories"]["absolute"]["words"]:
            if isinstance(w, str):
                absolute_words.add(w)
    for risk in risks:
        if risk["word"] not in absolute_words and risk["category"] != "绝对化用语":
            continue
        word = risk["word"]
        context = _get_context(text, risk["position"], len(word))
        if _is_enterprise_vision(context, word):
            risk["risk_level"] = "low"
            risk["suggest"] = "企业愿景表述，建议改为具体可验证的表述"
            risk["reason"] = "属于企业愿景类表述，不指向具体商品性能"
            continue
        if _is_limited_data(context, word):
            risk["risk_level"] = "medium"
            risk["needs_evidence"] = True
            risk["suggest"] = "需提供第三方证明材料并注明时间范围"
            risk["reason"] = "限定性数据宣称，需证据支持"
            continue
        if _is_legal_grade(context, word):
            risk["risk_level"] = "low"
            risk["suggest"] = "法定分级或真实获奖，需保留证明材料"
            risk["reason"] = "属于法定分级或获奖表述"
            continue
    return risks


def _apply_replace_suggestions(risks):
    for risk in risks:
        word = risk["word"]
        if word in _REPLACE_MAP:
            replace_to, note = _REPLACE_MAP[word]
            risk["replace_to"] = replace_to
            risk["suggest"] = f"将\"{word}\"改为\"{replace_to}\"，{note}"
        elif risk["type"] == "forbidden":
            if "replace_to" not in risk:
                risk["replace_to"] = ""
    return risks


def _get_context(text, position, word_len, window=30):
    start = max(0, position - window)
    end = min(len(text), position + word_len + window)
    return text[start:end]


def _is_enterprise_vision(context, word):
    return any(p in context for p in ("追求", "力争", "致力于", "愿景", "目标"))


def _is_limited_data(context, word):
    data_patterns = ("年", "月", "季度", "天猫", "京东", "抖音", "销量", "统计")
    count = sum(1 for p in data_patterns if p in context)
    return count >= 2


def _is_legal_grade(context, word):
    grade_patterns = ("特级", "一级", "二等奖", "三等奖", "金奖", "银奖", "认证", "标准")
    return any(p in context for p in grade_patterns)


def _map_severity_to_risk_level(severity):
    mapping = {"critical": "critical", "high": "high", "medium": "medium", "low": "low", "info": "info"}
    return mapping.get(severity, "high")


def _get_rule_layer(cat_key):
    layer_map = {
        "absolute": "A", "prohibited": "A", "false": "A", "health": "A",
        "cosmetics": "A", "medical_beauty": "A",
        "price_fraud": "B", "finance": "B", "education": "B", "real_estate": "B",
        "live_streaming": "C", "ecommerce": "C"
    }
    return layer_map.get(cat_key, "D")


def _get_default_suggest(cat_key):
    suggest_map = {
        "absolute": "删除绝对化用语，改为可验证的限定性表述",
        "prohibited": "删除违禁表述",
        "false": "删除虚假宣传内容，确保有证据支撑",
        "health": "删除功效夸大表述",
        "cosmetics": "删除化妆品违规表述",
        "medical_beauty": "删除医疗美容违规表述",
        "price_fraud": "删除价格欺诈表述，确保价格信息真实透明",
        "finance": "删除金融违规表述",
        "education": "删除教育培训违规表述",
        "real_estate": "删除房地产违规表述",
        "live_streaming": "删除直播违规表述",
        "ecommerce": "删除电商违规表述",
    }
    return suggest_map.get(cat_key, "建议删除或替换为合规表述")


def _calculate_score(risks):
    if not risks:
        return 100
    forbidden = [r for r in risks if r["type"] in ("forbidden", "industry")]
    if not forbidden:
        return 100
    penalty = sum(
        25 if r["risk_level"] == "critical" else
        15 if r["risk_level"] == "high" else
        8 if r["risk_level"] == "medium" else
        3 if r["risk_level"] == "low" else 0
        for r in forbidden
    )
    return max(0, 100 - penalty)


def _generate_summary(risks):
    forbidden = [r for r in risks if r["type"] in ("forbidden", "industry")]
    allowed = [r for r in risks if r["type"] == "allowed_with_filing"]
    if not forbidden and not allowed:
        return "未发现违规风险"
    parts = []
    if forbidden:
        c = sum(1 for r in forbidden if r["risk_level"] == "critical")
        h = sum(1 for r in forbidden if r["risk_level"] == "high")
        m = sum(1 for r in forbidden if r["risk_level"] == "medium")
        l = sum(1 for r in forbidden if r["risk_level"] == "low")
        detail = []
        if c: detail.append(f"明确违法{c}处")
        if h: detail.append(f"高风险{h}处")
        if m: detail.append(f"需优化{m}处")
        if l: detail.append(f"低风险{l}处")
        parts.append(f"发现{len(forbidden)}处违规风险：" + "、".join(detail))
    if allowed:
        parts.append(f"{len(allowed)}处需备案词")
    return "；".join(parts)


def _get_risk_distribution(risks):
    dist = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for r in risks:
        level = r.get("risk_level", "info")
        dist[level] = dist.get(level, 0) + 1
    return dist


def _generate_tips(risks, kb, industry="", platform=""):
    tips = []

    # 行业专项合规提示
    if industry == "fsmp":
        tips.extend([
            "特殊医学用途配方食品必须经国家市场监管总局注册，取得国食注字注册号",
            "广告不得涉及疾病预防、治疗功能，不得使用医疗用语",
            "标签必须标注适用人群、食用方法、警示说明",
            "0-12月龄产品不得进行广告宣传",
            "需标注'本品为特殊医学用途配方食品，需在医生或临床营养师指导下使用'",
        ])
    elif industry == "food":
        tips.append("食品广告不得涉及疾病预防、治疗功能宣称，不得使用医疗用语")
    else:
        tips.append("建议保留证据材料，检测报告、专利证书等需留存备查")

    needs_evidence = [r for r in risks if r.get("needs_evidence")]
    if needs_evidence:
        tips.append(f"有{len(needs_evidence)}处表述需提供证据支撑（检测报告/第三方证明等）")

    if platform and platform in _platform_tips:
        for tip in _platform_tips[platform]:
            tips.append(tip)

    forbidden = [r for r in risks if r["type"] in ("forbidden", "industry")]
    if forbidden:
        tips.append("依据《广告法》第九条：广告不得使用\"国家级\"\"最高级\"\"最佳\"等用语")
    if any(r["type"] == "forbidden" and r["risk_level"] in ("critical", "high") for r in risks):
        tips.append("建议在发布前修改违规表述，避免行政处罚风险")

    return tips
