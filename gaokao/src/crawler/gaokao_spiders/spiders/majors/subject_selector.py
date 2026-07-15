"""
新高考选科匹配数据模块

教育部《普通高校本科招生专业选考科目要求指引（通用版）》
3+1+2 模式下各选科组合可报考专业门类匹配规则。

数据来源：教育部官方发布标准，无需爬取，直接内置。
"""

# ── 12种选科组合定义 ──────────────────────────────────────────────

# 物理方向（6种）
COMBINATIONS = [
    # 组合编码, 显示名称, 物理/历史
    {"code": "物化生", "name": "物理+化学+生物", "group": "物理"},
    {"code": "物化地", "name": "物理+化学+地理", "group": "物理"},
    {"code": "物化政", "name": "物理+化学+政治", "group": "物理"},
    {"code": "物生地", "name": "物理+生物+地理", "group": "物理"},
    {"code": "物生政", "name": "物理+生物+政治", "group": "物理"},
    {"code": "物地政", "name": "物理+地理+政治", "group": "物理"},
    # 历史方向（6种）
    {"code": "史化生", "name": "历史+化学+生物", "group": "历史"},
    {"code": "史化地", "name": "历史+化学+地理", "group": "历史"},
    {"code": "史化政", "name": "历史+化学+政治", "group": "历史"},
    {"code": "史生地", "name": "历史+生物+地理", "group": "历史"},
    {"code": "史生政", "name": "历史+生物+政治", "group": "历史"},
    {"code": "史地政", "name": "历史+地理+政治", "group": "历史"},
]

# ── 专业门类分类 ──────────────────────────────────────────────────

# 所有专业门类（教育部本科专业目录12大学科门类下的专业大类）
ALL_CATEGORIES = [
    "哲学类", "经济学类", "法学类", "教育学类", "文学类",
    "历史学类", "理学类", "工学类", "农学类", "医学类",
    "管理学类", "艺术学类",
]

# 各学科大类包含的具体专业类
CATEGORY_DETAIL = {
    "哲学类": ["哲学类"],
    "经济学类": ["经济学类", "财政学类", "金融学类", "经济与贸易类"],
    "法学类": ["法学类", "政治学类", "社会学类", "民族学类", "马克思主义理论类", "公安学类"],
    "教育学类": ["教育学类", "体育学类"],
    "文学类": ["中国语言文学类", "外国语言文学类", "新闻传播学类"],
    "历史学类": ["历史学类"],
    "理学类": ["数学类", "物理学类", "化学类", "天文学类", "地理科学类",
                "大气科学类", "海洋科学类", "地球物理学类", "地质学类",
                "生物科学类", "心理学类", "统计学类"],
    "工学类": ["力学类", "机械类", "仪器类", "材料类", "能源动力类",
                "电气类", "电子信息类", "自动化类", "计算机类", "土木类",
                "水利类", "测绘类", "化工与制药类", "地质类", "矿业类",
                "纺织类", "轻工类", "交通运输类", "海洋工程类", "航空航天类",
                "兵器类", "核工程类", "农业工程类", "林业工程类", "环境科学与工程类",
                "生物医学工程类", "食品科学与工程类", "建筑类", "安全科学与工程类",
                "生物工程类", "公安技术类"],
    "农学类": ["植物生产类", "自然保护与环境生态类", "动物生产类",
                "动物医学类", "林学类", "水产类", "草学类"],
    "医学类": ["基础医学类", "临床医学类", "口腔医学类", "公共卫生与预防医学类",
                "中医学类", "中西医结合类", "药学类", "中药学类",
                "法医学类", "医学技术类", "护理学类"],
    "管理学类": ["管理科学与工程类", "工商管理类", "农业经济管理类",
                  "公共管理类", "图书情报与档案管理类", "物流管理与工程类",
                  "电子商务类", "旅游管理类"],
    "艺术学类": ["艺术学理论类", "音乐与舞蹈学类", "戏剧与影视学类",
                  "美术学类", "设计学类"],
}

# ── 教育部选考科目要求核心规则 ──────────────────────────────────

# 必选物理的专业类
MUST_PHYSICS = {
    "计算机类", "电子信息类", "自动化类", "机械类", "土木类",
    "电气类", "数学类", "统计学类", "物理学类", "大气科学类",
    "海洋科学类", "地质学类", "力学类", "材料类", "能源动力类",
    "仪器类", "水利类", "测绘类", "化工与制药类", "地质类",
    "矿业类", "纺织类", "轻工类", "交通运输类", "海洋工程类",
    "航空航天类", "兵器类", "核工程类", "农业工程类", "林业工程类",
    "环境科学与工程类", "食品科学与工程类", "建筑类", "安全科学与工程类",
    "生物工程类", "公安技术类", "管理科学与工程类",
}

# 必选化学的专业类
MUST_CHEMISTRY = {
    "化学类", "化工与制药类", "药学类", "中药学类",
}

# 必选物理+化学的专业类
MUST_PHYSICS_CHEMISTRY = {
    "临床医学类", "口腔医学类", "基础医学类",
}

# 必选历史的专业类
MUST_HISTORY = {
    "历史学类",
}
# 哲学类部分方向要求历史
MUST_HISTORY_PARTIAL = {
    "哲学类",
}

# 必选生物的专业类（部分学校要求）
MUST_BIOLOGY = {
    "生物科学类", "生物工程类",
}

# 必选政治的专业类
MUST_POLITICS = {
    "马克思主义理论类", "政治学类", "公安学类",
}

# ── 组合匹配规则计算 ──────────────────────────────────────────────

# 所有专业类的完整列表（用于统计总数）
ALL_DETAIL_CATEGORIES = []
for details in CATEGORY_DETAIL.values():
    ALL_DETAIL_CATEGORIES.extend(details)

TOTAL_DETAIL_CATEGORIES = len(ALL_DETAIL_CATEGORIES)

# 可报考限制明细（某些组合的特殊限制）
COMBINATION_RESTRICTIONS = {
    "物化生": {
        "description": "物化生组合，理工农医全覆盖，专业选择最广",
        "extra_restrictions": [],
    },
    "物化地": {
        "description": "物化地组合，理工类全覆盖，医农部分受限",
        "extra_restrictions": ["生物科学类", "生物工程类"],
    },
    "物化政": {
        "description": "物化政组合，理工+军警，报考公安类有优势",
        "extra_restrictions": ["生物科学类", "生物工程类"],
    },
    "物生地": {
        "description": "物生地组合，工学类受到较大限制",
        "extra_restrictions": ["化学类", "化工与制药类", "药学类", "中药学类",
                               "临床医学类", "口腔医学类", "基础医学类",
                               "生物科学类", "生物工程类"],
    },
    "物生政": {
        "description": "物生政组合，工学类受到较大限制",
        "extra_restrictions": ["化学类", "化工与制药类", "药学类", "中药学类",
                               "临床医学类", "口腔医学类", "基础医学类"],
    },
    "物地政": {
        "description": "物地政组合，工学类受严重限制",
        "extra_restrictions": ["化学类", "化工与制药类", "药学类", "中药学类",
                               "临床医学类", "口腔医学类", "基础医学类",
                               "生物科学类", "生物工程类"],
    },
    "史化生": {
        "description": "史化生组合，偏文兼医学，部分理工不能报",
        "extra_restrictions": MUST_PHYSICS,  # 不能报所有需物理的专业
    },
    "史化地": {
        "description": "史化地组合，偏文兼农化",
        "extra_restrictions": MUST_PHYSICS | {"生物科学类", "生物工程类"},
    },
    "史化政": {
        "description": "史化政组合，偏文兼军警",
        "extra_restrictions": MUST_PHYSICS | {"生物科学类", "生物工程类"},
    },
    "史生地": {
        "description": "史生地组合，偏文类+生物相关",
        "extra_restrictions": MUST_PHYSICS | {"化学类", "化工与制药类",
                                               "药学类", "中药学类",
                                               "临床医学类", "口腔医学类", "基础医学类"},
    },
    "史生政": {
        "description": "史生政组合，偏文类+军警",
        "extra_restrictions": MUST_PHYSICS | {"化学类", "化工与制药类",
                                               "药学类", "中药学类",
                                               "临床医学类", "口腔医学类", "基础医学类"},
    },
    "史地政": {
        "description": "史地政组合，传统文科，理工医均不能报",
        "extra_restrictions": MUST_PHYSICS | {"化学类", "化工与制药类",
                                               "药学类", "中药学类",
                                               "临床医学类", "口腔医学类", "基础医学类",
                                               "生物科学类", "生物工程类"},
    },
}


def get_available_categories(code: str) -> list[dict]:
    """
    根据选科组合编码，返回可报考的专业门类及详细信息。

    参数:
        code: 组合编码，如 '物化生', '史地政'

    返回:
        [
            {
                "category": "工学类",
                "detail_categories": ["力学类", "机械类", ...],
                "restricted": False
            },
            ...
        ]
    """
    restrictions = COMBINATION_RESTRICTIONS.get(code, {}).get("extra_restrictions", [])
    restricted_set = set(restrictions)

    result = []
    for cat in ALL_CATEGORIES:
        details = CATEGORY_DETAIL.get(cat, [])
        # 检查此门类下是否有被限制的专业大类
        restricted_details = [d for d in details if d in restricted_set]
        available_details = [d for d in details if d not in restricted_set]

        if available_details:
            result.append({
                "category": cat,
                "detail_categories": available_details,
                "restricted": len(restricted_details) > 0,
                "restricted_detail_categories": restricted_details if restricted_details else [],
            })
        elif restricted_details:
            # 所有子类都被限制
            pass  # 不添加

    return result


def calculate_match_rate(code: str) -> dict:
    """
    计算某组合的可报专业大类比例（基于全部专业类的计数）。

    返回:
        {
            "code": "物化生",
            "total_detail_categories": 96,
            "available_detail_categories": 96,
            "match_rate": 100.0,
            "total_categories": 12,
            "available_categories": 12,
            "categories": [...]
        }
    """
    available = get_available_categories(code)

    # 门类级计数
    available_cat_count = len(available)
    available_detail_count = sum(len(c["detail_categories"]) for c in available)
    total_cat = len(ALL_CATEGORIES)

    return {
        "code": code,
        "match_rate": round(available_detail_count / TOTAL_DETAIL_CATEGORIES * 100, 1),
        "total_detail_categories": TOTAL_DETAIL_CATEGORIES,
        "available_detail_categories": available_detail_count,
        "total_categories": total_cat,
        "available_categories": available_cat_count,
        "categories": available,
    }


def rank_combinations() -> list[dict]:
    """
    返回12种组合按可报比例降序排列。
    """
    results = []
    for c in COMBINATIONS:
        info = calculate_match_rate(c["code"])
        info["name"] = c["name"]
        info["group"] = c["group"]
        info["description"] = COMBINATION_RESTRICTIONS[c["code"]]["description"]
        results.append(info)

    results.sort(key=lambda x: x["match_rate"], reverse=True)
    return results


# ── 快速查询接口 ──────────────────────────────────────────────────

def get_combination_info(code: str) -> dict | None:
    """查询某个选科组合的详细信息"""
    for c in COMBINATIONS:
        if c["code"] == code:
            info = calculate_match_rate(code)
            info["name"] = c["name"]
            info["group"] = c["group"]
            info["description"] = COMBINATION_RESTRICTIONS[code]["description"]
            return info
    return None


def get_all_combinations() -> list[dict]:
    """获取所有12种组合的基本信息"""
    return COMBINATIONS


# ── 自测 ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  新高考3+1+2选科匹配数据")
    print("=" * 60)

    print("\n📊 所有组合可报考比例排名：\n")
    ranked = rank_combinations()
    for i, r in enumerate(ranked, 1):
        print(f"  {i:2d}. {r['code']:6s} ({r['name']:16s}) → 可报{r['available_detail_categories']:2d}/{r['total_detail_categories']}专业类 ({r['match_rate']}%)")

    print("\n📋 组合详情示例（物化生 vs 史地政）：\n")
    for code in ["物化生", "史地政"]:
        info = get_combination_info(code)
        if info:
            print(f"  [{code} {info['name']}] 可报 {info['available_detail_categories']}/{info['total_detail_categories']} 专业类 ({info['match_rate']}%)")
            print(f"  说明：{info['description']}")
            print(f"  可报门类：{', '.join(c['category'] for c in info['categories'])}")
            print()
