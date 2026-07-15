"""
图片处理工具 — 下载/格式统一/尺寸归一化/色彩优化/压缩
"""

from __future__ import annotations

import io
import logging
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import aiofiles
from PIL import Image, ImageEnhance

logger = logging.getLogger(__name__)

# 配置
MAX_WIDTH = 1920
JPEG_QUALITY = 90
SUPPORTED_FORMATS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


# ──────────────────────────────────────────────
# 图片标准化管线
# ──────────────────────────────────────────────

def standardize_image(
    input_path: str | Path,
    output_path: str | Path | None = None,
    max_width: int = MAX_WIDTH,
    quality: int = JPEG_QUALITY,
) -> Path:
    """
    将图片统一为 JPEG 格式，归一化宽度，增强对比度

    Args:
        input_path: 输入图片路径
        output_path: 输出路径（None 则覆盖原文件）
        max_width: 最大宽度（保持宽高比缩放）
        quality: JPEG 压缩质量

    Returns:
        处理后的图片路径
    """
    input_path = Path(input_path)
    if output_path is None:
        output_path = input_path.with_suffix(".jpg")

    img = Image.open(input_path)

    # 转换为 RGB（RGBA → RGB）
    if img.mode == "RGBA":
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # 尺寸归一化
    if img.width > max_width:
        ratio = max_width / img.width
        new_height = int(img.height * ratio)
        img = img.resize((max_width, new_height), Image.LANCZOS)

    # 对比度增强（有助于 OCR）
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.2)

    # 保存为 JPEG
    img.save(output_path, "JPEG", quality=quality)
    logger.info("图片标准化完成: %s → %s (%dx%d)", input_path, output_path, img.width, img.height)
    return Path(output_path)


def batch_standardize(
    input_paths: list[str | Path],
    output_dir: str | Path,
) -> list[Path]:
    """批量标准化图片"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    result_paths = []
    for path in input_paths:
        path = Path(path)
        out = output_dir / f"{path.stem}_std.jpg"
        try:
            standardized = standardize_image(path, out)
            result_paths.append(standardized)
        except Exception as exc:
            logger.error("图片标准化失败: %s — %s", path, exc)
            result_paths.append(path)  # 保底返回原路径

    return result_paths


# ──────────────────────────────────────────────
# 压缩
# ──────────────────────────────────────────────

def compress_image(
    input_path: str | Path,
    output_path: str | Path | None = None,
    max_size_kb: int = 500,
) -> Path:
    """
    压缩图片至指定大小以下（渐进式压缩）

    Args:
        input_path: 输入图片路径
        output_path: 输出路径
        max_size_kb: 目标最大 KB 数
    """
    input_path = Path(input_path)
    if output_path is None:
        output_path = input_path

    img = Image.open(input_path)
    quality = 85
    while quality > 10:
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=quality)
        if buf.tell() <= max_size_kb * 1024:
            with open(output_path, "wb") as f:
                f.write(buf.getvalue())
            return Path(output_path)
        quality -= 10

    # 最终尝试：缩小尺寸
    scale = 0.8
    while scale > 0.3:
        w = int(img.width * scale)
        h = int(img.height * scale)
        resized = img.resize((w, h), Image.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, "JPEG", quality=quality)
        if buf.tell() <= max_size_kb * 1024:
            with open(output_path, "wb") as f:
                f.write(buf.getvalue())
            return Path(output_path)
        scale -= 0.1

    return Path(output_path)


# ──────────────────────────────────────────────
# 压缩包处理
# ──────────────────────────────────────────────

async def extract_zip_archive(
    zip_path: str | Path,
    extract_dir: str | Path,
) -> list[Path]:
    """
    解压 ZIP 压缩包，返回支持的图片文件列表

    Args:
        zip_path: ZIP 文件路径
        extract_dir: 解压目标目录
    """
    zip_path = Path(zip_path)
    extract_dir = Path(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)

    extracted: list[Path] = []
    try:
        import aiofiles as _  # noqa: F401
        import zipfile

        with zipfile.ZipFile(zip_path, "r") as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                ext = Path(info.filename).suffix.lower()
                if ext not in SUPPORTED_FORMATS:
                    continue
                # 安全解压
                safe_name = Path(info.filename).name
                target = extract_dir / safe_name
                with zf.open(info) as source:
                    with open(target, "wb") as dest:
                        dest.write(source.read())
                extracted.append(target)

        logger.info("ZIP 解压完成: %s → %d 张图片", zip_path, len(extracted))
    except Exception as exc:
        logger.error("ZIP 解压失败: %s — %s", zip_path, exc)

    return extracted


# ──────────────────────────────────────────────
# 其他工具
# ──────────────────────────────────────────────

def is_image_file(path: str | Path) -> bool:
    """检查是否为支持的图片格式"""
    return Path(path).suffix.lower() in SUPPORTED_FORMATS


def get_image_size_mb(path: str | Path) -> float:
    """获取图片文件大小（MB）"""
    return os.path.getsize(path) / (1024 * 1024)


def ensure_temp_dir() -> Path:
    """获取图片处理的临时目录"""
    temp_dir = Path(tempfile.gettempdir()) / "ad-compliance" / "images"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir
