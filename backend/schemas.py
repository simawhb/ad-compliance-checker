"""数据模型定义 — 电商页面广告审查数据模型"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ════════════════════════════════════════════════
# 通用枚举
# ════════════════════════════════════════════════

class PlatformEnum(str, enum.Enum):
    """支持的电商平台"""
    STANDALONE = "standalone"      # 独立站/企业官网
    JD = "jd"                      # 京东
    TAOBAO = "taobao"              # 淘宝/天猫
    PINDUODUO = "pinduoduo"        # 拼多多
    DOUYIN = "douyin"              # 抖音小店
    MANUAL = "manual"              # 手工上传
    UNKNOWN = "unknown"            # 无法识别


class ViolationSeverity(str, enum.Enum):
    """违规严重程度"""
    CRITICAL = "严重"
    MEDIUM = "中等"
    MINOR = "轻微"


class RiskLevel(str, enum.Enum):
    """风险评估等级"""
    HIGH = "高风险"
    MEDIUM = "中风险"
    LOW = "低风险"


class ReviewChannel(str, enum.Enum):
    """审查渠道模式"""
    URL = "url"                    # URL 自动抓取
    UPLOAD = "upload"              # 截图上传


# ════════════════════════════════════════════════
# 抓取相关
# ════════════════════════════════════════════════

class ProductData(BaseModel):
    """从页面提取的结构化商品数据"""
    title: str = ""
    price: str = ""
    params: dict[str, str] = Field(default_factory=dict, description="商品参数键值对")
    description: str = ""
    raw_html: str = ""
    image_paths: list[str] = Field(default_factory=list, description="下载的详情图本地路径")
    screenshot_path: str = ""      # 页面截图路径
    platform: PlatformEnum = PlatformEnum.UNKNOWN
    url: str = ""


class PageData(BaseModel):
    """抓取 + OCR 合并后的完整页面数据"""
    url: str = ""
    platform: PlatformEnum = PlatformEnum.UNKNOWN
    title: str = ""
    price: str = ""
    params: dict[str, str] = Field(default_factory=dict)
    description: str = ""
    ocr_texts: list[str] = Field(default_factory=list, description="详情图 OCR 识别文本")
    screenshot_path: str = ""

    @property
    def all_text(self) -> str:
        """合并全部文字内容供 Lex 审查"""
        parts = [
            f"【标题】{self.title}",
            f"【价格】{self.price}",
            f"【参数】{chr(10).join(f'{k}: {v}' for k, v in self.params.items())}",
            f"【描述文字】{self.description}",
        ]
        if self.ocr_texts:
            parts.append(f"【详情图OCR结果】{chr(10).join(self.ocr_texts)}")
        return chr(10).join(parts)


# ════════════════════════════════════════════════
# 审查相关
# ════════════════════════════════════════════════

class ViolationItem(BaseModel):
    """单个违规点"""
    dimension: str = Field(..., description="审查维度：标题/价格/功效宣称/数据来源/资质/对比/极限词")
    content: str = Field(..., description="违规原文")
    severity: ViolationSeverity
    law_basis: str = Field(..., description="违反的具体法条")
    suggestion: str = Field(..., description="修改建议")
    rule_ids: list[str] = Field(default_factory=list, description="关联的已核验规则编号")
    penalty_reference: str = "",  # 典型处罚案例参考


class ReviewResult(BaseModel):
    """单次审查结果"""
    id: str                        # 审查记录 ID
    channel: ReviewChannel
    platform: PlatformEnum
    url: str = ""
    page_summary: str = ""         # 页面摘要信息
    violation_items: list[ViolationItem] = Field(default_factory=list)
    missing_materials: list[str] = Field(
        default_factory=list,
        description="完成事实核验仍需用户补充的证明、资质或数据来源",
    )
    risk_level: RiskLevel
    summary: str = ""              # 审查结论概述
    created_at: datetime = Field(default_factory=datetime.now)


# ════════════════════════════════════════════════
# API 请求/响应
# ════════════════════════════════════════════════

class CheckPageRequest(BaseModel):
    """URL 审查请求"""
    url: str = Field(..., description="电商产品页面 URL")


class CheckPageUploadRequest(BaseModel):
    """截图上传审查请求"""
    text: str = Field("", description="用户手动粘贴的商品标题/描述等文字")


class CheckPageResponse(BaseModel):
    """审查响应"""
    success: bool
    message: str = ""
    result: Optional[ReviewResult] = None
    error: str = ""


class OCRPreviewItem(BaseModel):
    """OCR 预览项（供用户手动修正）"""
    image_index: int
    image_filename: str
    recognized_text: str


class OCRPreviewResponse(BaseModel):
    """OCR 预览响应"""
    success: bool
    items: list[OCRPreviewItem] = Field(default_factory=list)
    merged_text: str = ""


# ════════════════════════════════════════════════
# 免费额度
# ════════════════════════════════════════════════

class QuotaInfo(BaseModel):
    """用户免费额度信息"""
    remaining: int
    total: int
    used_today: int
