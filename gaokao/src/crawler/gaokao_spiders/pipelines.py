"""
gaokao_spiders — Item Pipeline（数据管道）

当前直接导出 JSONL，管道留空供后续扩展：
- 数据校验（调用 src/etl/data_validator.py）
- PostgreSQL 批量入库
- 去重处理
"""


class GaokaoSpidersPipeline:
    """默认管道（占位）"""

    def process_item(self, item, spider):
        return item
