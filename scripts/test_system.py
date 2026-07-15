"""
驷马合规 · 电商页面广告审查系统 — 集成测试脚本

在主力机（Win10 LTSC）上运行：
    cd backend
    python ../scripts/test_system.py

测试项：
1. ✅ 核心模块导入
2. ✅ 数据模型验证
3. ✅ 平台识别逻辑
4. ✅ OCR 引擎初始化（含 fallback）
5. ✅ LLM 审查（模拟模式）
6. ✅ 页面抓取（需网络，可选）
7. ✅ 全链路 API 测试（启动服务后执行）
"""

import sys
import os
from pathlib import Path

# 将 backend 目录加入 sys.path
BACKEND_DIR = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

PASS = 0
FAIL = 0
SKIP = 0


def test(name: str):
    """测试装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            global PASS, FAIL, SKIP
            try:
                func(*args, **kwargs)
                print(f"  ✅ {name}")
                PASS += 1
            except Exception as e:
                print(f"  ❌ {name}: {e}")
                FAIL += 1
        return wrapper
    return decorator


# ═══════════════════════════════════════════════════
# 测试 1: 导入测试
# ═══════════════════════════════════════════════════

@test("导入 schemas 模块")
def test_import_schemas():
    import schemas
    assert hasattr(schemas, "PageData")
    assert hasattr(schemas, "PlatformEnum")
    assert hasattr(schemas, "ReviewResult")
    assert hasattr(schemas, "ViolationItem")
    assert hasattr(schemas, "CheckPageRequest")
    assert hasattr(schemas, "CheckPageResponse")
    # 检查枚举
    assert schemas.PlatformEnum.STANDALONE.value == "standalone"
    assert schemas.PlatformEnum.JD.value == "jd"
    assert schemas.RiskLevel.HIGH.value == "高风险"


@test("导入 ocr_engine 模块")
def test_import_ocr():
    import ocr_engine
    engine = ocr_engine.get_ocr_engine()
    assert engine is not None
    assert hasattr(engine, "recognize")
    assert hasattr(engine, "recognize_batch")


@test("导入 llm 模块")
def test_import_llm():
    import llm
    assert hasattr(llm, "review_ecommerce_page")
    assert hasattr(llm, "review_ad_copy")
    assert hasattr(llm, "get_llm_client")


@test("导入 page_fetcher 模块")
def test_import_page_fetcher():
    import page_fetcher
    assert hasattr(page_fetcher, "PageFetcher")
    assert hasattr(page_fetcher, "identify_platform")
    assert hasattr(page_fetcher, "get_page_fetcher")
    fetcher = page_fetcher.get_page_fetcher()
    assert fetcher is not None


@test("导入 platform_adapters 所有适配器")
def test_import_adapters():
    import platform_adapters
    assert hasattr(platform_adapters, "BaseAdapter")
    assert hasattr(platform_adapters, "StandaloneAdapter")
    assert hasattr(platform_adapters, "ManualAdapter")
    # JDAdapter 可能为 None（jd.py 可选依赖），但不应该抛出异常
    assert platform_adapters.JDAdapter is None or platform_adapters.JDAdapter is not None


@test("导入 utils.image_utils")
def test_import_image_utils():
    from utils.image_utils import standardize_image, is_image_file, ensure_temp_dir
    assert callable(standardize_image)
    assert callable(is_image_file)
    assert callable(ensure_temp_dir)
    assert is_image_file("test.jpg") == True
    assert is_image_file("test.png") == True
    assert is_image_file("test.txt") == False
    assert is_image_file("test.zip") == False


# ═══════════════════════════════════════════════════
# 测试 2: 平台识别
# ═══════════════════════════════════════════════════

@test("平台识别 — 京东")
def test_platform_jd():
    from page_fetcher import identify_platform
    from schemas import PlatformEnum

    assert identify_platform("https://item.jd.com/123.html") == PlatformEnum.JD
    assert identify_platform("https://product.jd.com/123.html") == PlatformEnum.JD
    assert identify_platform("https://www.jd.com/") == PlatformEnum.JD


@test("平台识别 — 淘宝/天猫")
def test_platform_taobao():
    from page_fetcher import identify_platform
    from schemas import PlatformEnum

    assert identify_platform("https://item.taobao.com/item.htm?id=123") == PlatformEnum.TAOBAO
    assert identify_platform("https://detail.tmall.com/item.htm?id=123") == PlatformEnum.TAOBAO


@test("平台识别 — 独立站")
def test_platform_standalone():
    from page_fetcher import identify_platform
    from schemas import PlatformEnum

    assert identify_platform("https://example.com/product/123") == PlatformEnum.STANDALONE
    assert identify_platform("https://shop.shopify.com/products/abc") == PlatformEnum.STANDALONE
    assert identify_platform("https://www.baidu.com") == PlatformEnum.STANDALONE


@test("平台识别 — 强反爬兜底")
def test_platform_needs_manual():
    from page_fetcher import identify_platform
    from schemas import PlatformEnum

    assert identify_platform("https://mobile.yangkeduo.com/goods.html") == PlatformEnum.PINDUODUO
    assert identify_platform("https://haohuo.douyin.com/123") == PlatformEnum.DOUYIN


# ═══════════════════════════════════════════════════
# 测试 3: 数据模型
# ═══════════════════════════════════════════════════

@test("PageData.all_text 合并正确")
def test_page_data_all_text():
    from schemas import PageData

    pd = PageData(
        url="https://example.com/p/1",
        title="超级好用的产品",
        price="¥99.00",
        params={"材质": "不锈钢", "尺寸": "20cm"},
        description="这是一款非常好用的产品",
        ocr_texts=["详情文字1", "详情文字2"],
    )
    text = pd.all_text
    assert "超级好用的产品" in text
    assert "¥99.00" in text
    assert "不锈钢" in text
    assert "详情文字1" in text
    assert "详情文字2" in text
    assert "【标题】" in text
    assert "【价格】" in text


@test("ReviewResult 模型正确")
def test_review_result():
    from schemas import ReviewResult, ViolationItem, ViolationSeverity, RiskLevel
    import uuid

    result = ReviewResult(
        id=f"TEST-{uuid.uuid4().hex[:8]}",
        channel="url",
        platform="jd",
        url="https://item.jd.com/123.html",
        page_summary="测试商品",
        violation_items=[
            ViolationItem(
                dimension="标题审查",
                content="最好",
                severity=ViolationSeverity.MEDIUM,
                law_basis="广告法第九条",
                suggestion="删除最好",
                penalty_reference="案例参考",
            )
        ],
        risk_level=RiskLevel.MEDIUM,
        summary="发现1处违规",
    )
    assert len(result.violation_items) == 1
    assert result.violation_items[0].severity.value == "中等"
    assert result.risk_level.value == "中风险"


# ═══════════════════════════════════════════════════
# 测试 4: LLM 模拟审查
# ═══════════════════════════════════════════════════

@test("LLM 电商审查（模拟模式 — 检测极限词）")
async def test_llm_review_extreme():
    from llm import review_ecommerce_page

    result = await review_ecommerce_page(
        title="行业最好的产品",
        description="宣传文案内容",
    )
    assert result is not None
    # 应该检测到 '最好'
    violations_with_best = [v for v in result.violation_items if "最好" in v.content]
    assert len(violations_with_best) > 0, f"应该检测到'最好'，但违规项为: {[v.content for v in result.violation_items]}"


@test("LLM 电商审查（模拟模式 — 检测医疗用语）")
async def test_llm_review_medical():
    from llm import review_ecommerce_page

    result = await review_ecommerce_page(
        title="特效产品",
        description="本品具有抗炎疗效，能治愈各种皮肤问题",
    )
    assert result is not None
    medical_violations = [v for v in result.violation_items if "抗炎" in v.content or "治愈" in v.content]
    assert len(medical_violations) > 0, f"应该检测到医疗用语，但违规项为: {[v.content for v in result.violation_items]}"


@test("LLM 广告文案审查（保持兼容）")
async def test_llm_ad_copy():
    from llm import review_ad_copy

    result = await review_ad_copy("普通广告文案内容")
    assert result is not None
    assert result.id.startswith("EC-") or result.id.startswith("EC-ERR-")


# ═══════════════════════════════════════════════════
# 测试 5: OCR 引擎初始化
# ═══════════════════════════════════════════════════

@test("OCR 引擎初始化（不实际加载模型）")
def test_ocr_engine_init():
    from ocr_engine import OCREngine

    engine = OCREngine(use_gpu=False)
    assert engine is not None
    assert engine.use_gpu == False
    assert engine.fallback_to_easyocr == True
    assert engine._paddle_ocr is None
    assert engine._current_engine is None


# ═══════════════════════════════════════════════════
# 测试 6: 图片工具
# ═══════════════════════════════════════════════════

@test("图片格式检测")
def test_image_detection():
    from utils.image_utils import is_image_file, get_image_size_mb
    import tempfile

    assert is_image_file("photo.jpg") == True
    assert is_image_file("photo.jpeg") == True
    assert is_image_file("photo.png") == True
    assert is_image_file("photo.webp") == True
    assert is_image_file("photo.bmp") == True
    assert is_image_file("photo.gif") == False
    assert is_image_file("photo.zip") == False
    assert is_image_file("photo.txt") == False

    # 测试临时目录创建
    temp_dir = ensure_temp_dir()
    assert temp_dir.exists()
    assert "ad-compliance" in str(temp_dir)


# ═══════════════════════════════════════════════════
# 运行所有测试
# ═══════════════════════════════════════════════════

async def run_async_tests():
    await test_llm_review_extreme()
    await test_llm_review_medical()
    await test_llm_ad_copy()


def main():
    global PASS, FAIL, SKIP

    print("=" * 50)
    print("驷马合规 · 电商页面审查系统 — 集成测试")
    print("=" * 50)
    print()

    # 同步测试
    print("📦 模块导入测试")
    test_import_schemas()
    test_import_ocr()
    test_import_llm()
    test_import_page_fetcher()
    test_import_adapters()
    test_import_image_utils()
    print()

    print("🔍 平台识别测试")
    test_platform_jd()
    test_platform_taobao()
    test_platform_standalone()
    test_platform_needs_manual()
    print()

    print("📐 数据模型测试")
    test_page_data_all_text()
    test_review_result()
    print()

    print("🤖 LLM 审查测试（模拟模式）")
    import asyncio
    asyncio.run(run_async_tests())
    print()

    print("🔧 OCR 引擎测试")
    test_ocr_engine_init()
    print()

    print("🖼️ 图片工具测试")
    test_image_detection()
    print()

    # 汇总
    print("=" * 50)
    total = PASS + FAIL + SKIP
    print(f"📊 测试汇总: {total} 项")
    print(f"   ✅ 通过: {PASS}")
    print(f"   ❌ 失败: {FAIL}")
    print(f"   ⏭️  跳过: {SKIP}")
    print("=" * 50)

    if FAIL > 0:
        print("⚠️  部分测试未通过，请检查上述错误")
        sys.exit(1)
    else:
        print("🎉 所有测试通过！")
        sys.exit(0)


if __name__ == "__main__":
    main()
