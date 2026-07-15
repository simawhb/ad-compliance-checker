# -*- coding: utf-8 -*-
"""邮件发送模块"""
import smtplib
import os
import logging
from email.mime.text import MIMEText
from email.header import Header

logger = logging.getLogger(__name__)

SMTP_HOST = "smtp.qq.com"
SMTP_PORT = 587
FROM_EMAIL = "14712502@qq.com"
AUTH_CODE_ENV = "QQ_MAIL_AUTH"

def send(subject: str, body: str, to_email: str = "14712502@qq.com") -> bool:
    auth_code = os.environ.get(AUTH_CODE_ENV, "")
    if not auth_code:
        logger.warning(f"未设置 {AUTH_CODE_ENV} 环境变量，跳过邮件发送")
        return False
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email
    msg["Subject"] = Header(subject, "utf-8")
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(FROM_EMAIL, auth_code)
            server.sendmail(FROM_EMAIL, [to_email], msg.as_string())
        logger.info(f"邮件已发送: {subject} -> {to_email}")
        return True
    except Exception as e:
        logger.error(f"邮件发送失败: {e}")
        return False
