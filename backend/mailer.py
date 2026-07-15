"""邮件发送模块 — 沿用现有实现，适配电商报告发送"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def send_report_email(
    to_email: str,
    subject: str,
    body: str,
    attachment_path: str = "",
):
    """
    发送合规报告邮件

    Args:
        to_email: 收件人邮箱
        subject: 邮件主题
        body: 邮件正文
        attachment_path: PDF 附件路径（可选）
    """
    # TODO: 接入实际邮件服务（SMTP 或 SendGrid 等）
    logger.info(
        "发送邮件: to=%s | subject=%s | attachment=%s",
        to_email, subject, attachment_path,
    )
    pass  # 保持与现有实现一致
