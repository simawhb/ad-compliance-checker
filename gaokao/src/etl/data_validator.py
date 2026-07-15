"""
data_validator.py — 数据校验模块
每条数据入库前必须调对应校验函数通过。
返回空列表表示校验通过，返回错误列表表示不合格。
"""

from typing import Any


def validate_school(record: dict) -> list[str]:
    """校验院校数据"""
    errors = []

    # 必填字段检查
    for field in ["code_edu", "name", "province", "level"]:
        if not record.get(field):
            errors.append(f"[schools] 必填字段缺失: {field}")

    # 字段格式检查
    if record.get("code_edu") and not str(record["code_edu"]).isdigit():
        errors.append(f"[schools] code_edu 必须是数字: {record['code_edu']}")
    if record.get("code_edu") and len(str(record["code_edu"])) != 5:
        errors.append(f"[schools] code_edu 必须是5位数字: {record['code_edu']}")

    if record.get("name") and len(str(record["name"]).strip()) < 2:
        errors.append(f"[schools] name 长度异常: {record['name']}")

    # level 取值范围
    valid_levels = ["本科", "专科", "职业本科"]
    if record.get("level") and record["level"] not in valid_levels:
        errors.append(f"[schools] level 值非法: {record['level']}（合法值: {valid_levels}）")

    # 办学类型取值范围
    valid_types = [
        "综合", "理工", "农林", "医药", "师范", "语言",
        "财经", "政法", "体育", "艺术", "军事", "民族"
    ]
    if record.get("type") and record["type"] not in valid_types:
        errors.append(f"[schools] type 值非法: {record['type']}")

    # 数据来源检查
    if not record.get("data_source"):
        errors.append("[schools] data_source 不能为空")

    return errors


def validate_major(record: dict) -> list[str]:
    """校验专业数据"""
    errors = []

    for field in ["major_id", "name", "category_id", "level"]:
        if not record.get(field):
            errors.append(f"[majors] 必填字段缺失: {field}")

    if record.get("major_id") and len(str(record["major_id"]).strip()) < 2:
        errors.append(f"[majors] major_id 长度异常: {record['major_id']}")

    valid_levels = ["本科", "专科"]
    if record.get("level") and record["level"] not in valid_levels:
        errors.append(f"[majors] level 值非法: {record['level']}")

    if record.get("version_year") and not isinstance(record["version_year"], int):
        errors.append(f"[majors] version_year 必须是整数: {record['version_year']}")

    if not record.get("data_source"):
        errors.append("[majors] data_source 不能为空")

    return errors


def validate_admission(record: dict) -> list[str]:
    """校验录取数据——核心校验函数"""
    errors = []

    # 必填字段
    for field in ["school_id", "province", "year", "student_category"]:
        if not record.get(field):
            errors.append(f"[admission] 必填字段缺失: {field}")

    # 年份合理性
    if record.get("year"):
        year = int(record["year"])
        if year < 2010 or year > 2027:
            errors.append(f"[admission] year 超出合理范围: {year}")
    else:
        errors.append("[admission] year 不能为空")

    # 分数逻辑
    if record.get("admit_score_min") is not None:
        min_score = float(record["admit_score_min"])
        if min_score <= 0:
            errors.append(f"[admission] admit_score_min 必须大于0: {min_score}")
        if min_score > 780:
            errors.append(f"[admission] admit_score_min 超过合理范围: {min_score}（满分一般750）")

    if record.get("admit_score_max") is not None and record.get("admit_score_min") is not None:
        if float(record["admit_score_max"]) < float(record["admit_score_min"]):
            errors.append(f"[admission] admit_score_max < admit_score_min: {record['admit_score_max']} < {record['admit_score_min']}")

    if record.get("admit_score_avg") is not None and record.get("admit_score_min") is not None:
        if float(record["admit_score_avg"]) < float(record["admit_score_min"]):
            errors.append(f"[admission] admit_score_avg < admit_score_min")
    if record.get("admit_score_avg") is not None and record.get("admit_score_max") is not None:
        if float(record["admit_score_avg"]) > float(record["admit_score_max"]):
            errors.append(f"[admission] admit_score_avg > admit_score_max")

    # 位次逻辑
    if record.get("admit_rank_min") is not None:
        rank = int(record["admit_rank_min"])
        if rank <= 0:
            errors.append(f"[admission] admit_rank_min 必须大于0: {rank}")
        if rank > 100_000_000:
            errors.append(f"[admission] admit_rank_min 超出合理范围: {rank}")

    if record.get("admit_rank_max") is not None and record.get("admit_rank_min") is not None:
        if int(record["admit_rank_max"]) < int(record["admit_rank_min"]):
            errors.append(f"[admission] admit_rank_max < admit_rank_min")

    # 计划人数
    if record.get("plan_count") is not None:
        if int(record["plan_count"]) < 0:
            errors.append(f"[admission] plan_count 不能为负数: {record['plan_count']}")
        if int(record["plan_count"]) > 100_000:
            errors.append(f"[admission] plan_count 超出合理范围: {record['plan_count']}")

    # 批次
    valid_batch_prefixes = ["本科", "专科", "提前", "艺术", "体育", "强基"]
    if record.get("batch"):
        has_prefix = any(str(record["batch"]).startswith(p) for p in valid_batch_prefixes)
        if not has_prefix:
            errors.append(f"[admission] batch 值疑似异常: {record['batch']}")

    # 考生类别
    valid_categories = ["文科", "理科", "综合", "物理类", "历史类", "不分文理"]
    if record.get("student_category") and record["student_category"] not in valid_categories:
        errors.append(f"[admission] student_category 值非法: {record['student_category']}")

    if not record.get("data_source"):
        errors.append("[admission] data_source 不能为空")

    return errors


def validate_score_line(record: dict) -> list[str]:
    """校验省控线"""
    errors = []

    for field in ["province", "year", "batch", "student_category", "score_line"]:
        if record.get(field) is None:
            errors.append(f"[province_score_lines] 必填字段缺失: {field}")

    if record.get("score_line") is not None and float(record["score_line"]) <= 0:
        errors.append(f"[province_score_lines] score_line 必须 > 0: {record['score_line']}")

    if record.get("score_line") is not None and float(record["score_line"]) > 780:
        errors.append(f"[province_score_lines] score_line 超出合理范围: {record['score_line']}")

    return errors


def validate_score_rank(record: dict) -> list[str]:
    """校验一分一段表"""
    errors = []

    for field in ["province", "year", "student_category", "score", "cumulative_count"]:
        if record.get(field) is None:
            errors.append(f"[score_rank_segments] 必填字段缺失: {field}")

    if record.get("score") is not None:
        score = float(record["score"])
        if score < 0 or score > 780:
            errors.append(f"[score_rank_segments] score 超出合理范围: {score}")

    if record.get("cumulative_count") is not None and int(record["cumulative_count"]) <= 0:
        errors.append(f"[score_rank_segments] cumulative_count 必须 > 0: {record['cumulative_count']}")

    if record.get("rank_start") is not None and record.get("rank_end") is not None:
        if int(record["rank_end"]) < int(record["rank_start"]):
            errors.append(f"[score_rank_segments] rank_end < rank_start")

    return errors


def validate_policy(record: dict) -> list[str]:
    """校验招生政策"""
    errors = []

    for field in ["title", "province", "year", "url"]:
        if not record.get(field):
            errors.append(f"[policies] 必填字段缺失: {field}")

    if record.get("voting_rule") and record["voting_rule"] not in ["平行志愿", "顺序志愿", "平行志愿+顺序志愿"]:
        errors.append(f"[policies] voting_rule 值非法: {record['voting_rule']}")

    if record.get("admission_rule") and record["admission_rule"] not in ["分数优先", "专业优先", "专业级差"]:
        errors.append(f"[policies] admission_rule 值非法: {record['admission_rule']}")

    return errors


def validate_employment(record: dict) -> list[str]:
    """校验就业数据"""
    errors = []

    if not record.get("school_id") and not record.get("major_id"):
        errors.append("[employment] school_id 和 major_id 至少需要一个")

    if not record.get("year"):
        errors.append("[employment] year 不能为空")
    else:
        year = int(record["year"])
        if year < 2015 or year > 2027:
            errors.append(f"[employment] year 超出合理范围: {year}")

    if record.get("employment_rate") is not None:
        rate = float(record["employment_rate"])
        if rate < 0 or rate > 100:
            errors.append(f"[employment] employment_rate 取值范围应为 0-100: {rate}")

    if record.get("salary_avg") is not None and int(record["salary_avg"]) <= 0:
        errors.append(f"[employment] salary_avg 必须 > 0: {record['salary_avg']}")

    return errors


def validate_ranking(record: dict) -> list[str]:
    """校验排名数据"""
    errors = []

    for field in ["ranking_name", "ranking_year", "school_id", "rank"]:
        if not record.get(field):
            errors.append(f"[rankings] 必填字段缺失: {field}")

    valid_rankings = ["软科中国大学排名", "软科世界大学排名", "校友会排名",
                      "QS世界大学排名", "US News排名", "THE泰晤士排名",
                      "教育部学科评估", "ESI学科排名"]
    if record.get("ranking_name") and record["ranking_name"] not in valid_rankings:
        errors.append(f"[rankings] ranking_name 不在已知列表中: {record['ranking_name']}（如需添加请先更新校验规则）")

    if record.get("rank") is not None:
        r = int(record["rank"])
        if r <= 0:
            errors.append(f"[rankings] rank 必须 > 0: {r}")
        if record.get("rank_total") and r > int(record["rank_total"]):
            errors.append(f"[rankings] rank 不能大于 rank_total: {r} > {record['rank_total']}")

    return errors


def validate_user_review(record: dict) -> list[str]:
    """校验用户评价数据"""
    errors = []

    for field in ["school_id", "platform", "platform_url"]:
        if not record.get(field):
            errors.append(f"[user_reviews] 必填字段缺失: {field}")

    valid_platforms = ["知乎", "小红书", "百度贴吧", "豆瓣", "B站", "掌上高考", "抖音", "快手"]
    if record.get("platform") and record["platform"] not in valid_platforms:
        errors.append(f"[user_reviews] platform 不在已知列表中: {record['platform']}")

    if record.get("sentiment") and record["sentiment"] not in ["positive", "negative", "neutral"]:
        errors.append(f"[user_reviews] sentiment 值非法: {record['sentiment']}")

    if record.get("author_id") and len(str(record["author_id"])) == 0:
        errors.append("[user_reviews] author_id 为空字符串（应使用 MD5 哈希或 null）")

    if record.get("data_source") and "user_reviews" not in str(record["data_source"]):
        pass  # user_reviews 的 data_source 可以不包含表名

    if not record.get("data_source"):
        errors.append("[user_reviews] data_source 不能为空")

    return errors


# ========== 通用批量校验函数 ==========

def validate_batch(records: list[dict], table_name: str) -> dict:
    """
    批量校验数据，返回统计信息。

    参数:
        records: 要校验的数据列表
        table_name: 表名（schools/majors/admission/...）

    返回:
        {
            "total": int,           # 总记录数
            "passed": int,          # 通过数
            "failed": int,          # 失败数
            "pass_rate": float,     # 通过率
            "failed_records": list, # 失败记录（含索引和错误原因）
            "error_summary": dict   # 错误类型统计
        }
    """
    VALIDATORS = {
        "schools": validate_school,
        "majors": validate_major,
        "admission": validate_admission,
        "province_score_lines": validate_score_line,
        "score_rank_segments": validate_score_rank,
        "policies": validate_policy,
        "employment": validate_employment,
        "rankings": validate_ranking,
        "user_reviews": validate_user_review,
    }

    validator = VALIDATORS.get(table_name)
    if not validator:
        return {"error": f"未知表名: {table_name}，可用表名: {list(VALIDATORS.keys())}"}

    passed = 0
    failed = 0
    failed_records = []
    error_summary = {}

    for idx, record in enumerate(records):
        errors = validator(record)
        if errors:
            failed += 1
            failed_records.append({
                "index": idx,
                "record_id": record.get("id", record.get("major_id", record.get("code_edu", idx))),
                "errors": errors,
            })
            for err in errors:
                err_type = err.split("]")[0] + "]" if "]" in err else "通用"
                error_summary[err_type] = error_summary.get(err_type, 0) + 1
        else:
            passed += 1

    total = len(records)
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": round(passed / total * 100, 2) if total > 0 else 0,
        "failed_records": failed_records,
        "error_summary": error_summary,
    }


def quality_gate(records: list[dict], table_name: str, batch_config: dict) -> dict:
    """
    质量门禁检查 — 在入库前执行
    
    返回:
        {
            "decision": "pass" | "reject" | "pass_with_warnings",
            "reasons": [...],
            "stats": {...}
        }
    """
    result = validate_batch(records, table_name)
    
    # 一票否决检查
    if result["total"] == 0:
        return {"decision": "reject", "reasons": ["没有数据"]}
    
    pass_rate = result["pass_rate"]
    reasons = []
    
    # 致命：通过率低于 95%
    if pass_rate < 95:
        reasons.append(f"通过率 {pass_rate}% 低于阈值 95%")
    
    # 致命：关键字段缺失比例
    key_fields = ["province", "year", "data_source"]
    missing_key_rate = sum(
        1 for r in records if any(r.get(f) is None for f in key_fields)
    ) / len(records)
    if missing_key_rate > 0.05:
        reasons.append(f"关键字段缺失率 {missing_key_rate*100:.1f}% 超过 5%")
    
    # 致命：一致性冲突
    if table_name == "admission":
        conflict_count = sum(
            1 for r in records
            if r.get("admit_score_max") is not None
            and r.get("admit_score_min") is not None
            and float(r["admit_score_max"]) < float(r["admit_score_min"])
        )
        if conflict_count > 0:
            reasons.append(f"存在 {conflict_count} 条分数逻辑冲突记录")
    
    # 判定
    if reasons:
        return {"decision": "reject", "reasons": reasons, "stats": result}
    
    # 检查是否存在警告
    warnings = []
    if result["failed"] > 0:
        warnings.append(f"{result['failed']} 条数据校验失败（已写入 errors）")
    
    decision = "pass" if not warnings else "pass_with_warnings"
    return {"decision": decision, "reasons": reasons + warnings, "stats": result}


