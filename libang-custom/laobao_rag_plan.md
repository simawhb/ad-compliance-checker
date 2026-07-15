# 驷马用工宝 — RAG 案例库技术方案

> 劳动法 AI 问答助手的检索增强生成（Retrieval-Augmented Generation）方案
>
> 文档版本: v1.0 | 2026-07-11

---

## 目录

1. [架构设计](#1-架构设计)
2. [技术选型](#2-技术选型)
3. [案例数据方案](#3-案例数据方案)
4. [检索与生成流程](#4-检索与生成流程)
5. [实施计划](#5-实施计划)
6. [效果评估](#6-效果评估)
7. [附录：完整代码清单](#7-附录完整代码清单)

---

## 1. 架构设计

### 1.1 当前架构与问题

现有系统采用两层问答：

```
用户提问
    │
    ├── FAQ 匹配（关键词 → 预写答案）── 命中则秒回
    │
    └── AI 直接生成（DeepSeek API）── 纯靠模型知识
```

**问题：**

- AI 回答缺乏真实判例支撑，用户无法看到"类似案件如何判决"
- 模型可能产生 Hallucination，编造法条或案例
- 知识库只存储法规原文，没有案例数据
- 不支持引用来源（当前 `citations` 字段始终为空数组）

### 1.2 目标架构（引入 RAG）

```
用户提问
    │
    ├── FAQ 匹配（关键词 → 预写答案）── 命中则秒回
    │
    └── RAG 增强生成
            │
            ├── 1. Query 理解与改写
            │       └── 提取案由、关键词、地区、时间范围
            │
            ├── 2. 向量检索（Chroma）
            │       ├── 案例向量库（裁判文书）
            │       └── 法规向量库（劳动法相关条款）
            │
            ├── 3. 重排序（Cross-encoder）
            │       └── 精排 Top-K 条相关案例
            │
            ├── 4. Prompt 拼接
            │       └── System Prompt + 参考案例 + 用户问题
            │
            └── 5. AI 生成（DeepSeek）
                    └── 流式输出 + 引用标注
```

### 1.3 数据流图

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  用户提问     │────→│  chat.py         │────→│  faq_service     │
│  POST /chat   │     │  _chat_common()  │     │  match()         │
└──────────────┘     └──────────────────┘     └──────────────────┘
                              │                       │
                              │ FAQ 未命中            │ FAQ 命中
                              ▼                       ▼
                     ┌──────────────────┐    ┌──────────────────┐
                     │  rag_service     │    │  直接返回        │
                     │  retrieve()      │    │  FAQ 答案        │
                     └──────────────────┘    └──────────────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │  Chroma 向量库   │
                     │  (案例 + 法规)   │
                     └──────────────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │  Cross-encoder   │
                     │  重排序          │
                     └──────────────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │  Prompt 拼接     │
                     │  + 引用格式化    │
                     └──────────────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │  ai_service      │
                     │  chat_stream()   │
                     └──────────────────┘
                              │
                              ▼
                     ┌──────────────────┐
                     │  SSE 流式响应     │
                     │  含 citations[]   │
                     └──────────────────┘
```

### 1.4 与现有 chat.py 的集成方式

**最小入侵原则**：不重构现有代码，只新增一个 `rag_service`，在 `_chat_common` 中插入一个可选的 RAG 步骤。

修改点（共 3 处）：

1. **chat.py** — 在 `_chat_common` 中，FAQ 未命中之后、调用 AI 之前，插入 RAG 检索
2. **ai_service.py** — 新增 `chat_stream_with_context()` 方法，接收额外 context 参数
3. **config.py** — 新增 RAG 相关配置项

修改后的 `_chat_common` 核心逻辑：

```python
# ---- 第二步：FAQ 未命中，走 RAG + AI ----
# RAG 检索
if settings.rag_enabled:
    rag_context = rag_service.retrieve(user_message, top_k=5)
    citations = rag_context.get("citations", [])
    reference_cases = rag_context.get("reference_cases", [])
else:
    citations = []
    reference_cases = []

# 构建含案例引用的 prompt
user_prompt = build_user_prompt_func(user_message, {
    "reference_cases": reference_cases,
    "citations": citations,
})

async def event_generator():
    # ... 流式输出 ...
    yield {
        "event": "message",
        "data": json.dumps({
            "token": "", "done": True,
            "intent": intent,
            "source": "rag",       # 标记来源为 RAG
            "citations": [c.dict() for c in citations],
        }),
    }
```

---

## 2. 技术选型

### 2.1 向量数据库：Chroma

| 项目 | 选择 | 理由 |
|------|------|------|
| **库名** | Chroma (`chromadb`) |  |
| **部署方式** | 嵌入式（in-process） | 无需独立服务进程 |
| **存储后端** | DuckDB + Parquet（持久化到磁盘） | 重启不丢数据 |
| **索引类型** | HNSW（默认） | 适合 1 万 ~ 10 万级别数据 |

**选择理由：**

1. **零运维** — 嵌入式运行，无需启动额外容器或服务，与现有 SQLite 数据库理念一致
2. **Python 原生** — `pip install chromadb` 即可使用，与 FastAPI 同一进程
3. **持久化** — 数据保存在本地磁盘文件，重启不丢失
4. **性能充足** — 10 万条以下案例数据，HNSW 索引检索 < 100ms
5. **元数据过滤** — 支持按案由、地区、年份等字段过滤后再检索
6. **对比其他方案：**
   - Milvus：功能强大但需要独立部署，运维成本高，当前阶段不需要分布式能力
   - Pinecone：SaaS 服务，数据需上传云端，不适合本地部署
   - FAISS：只做索引不做存储，需自行管理数据持久化
   - Qdrant：需要独立服务，相比 Chroma 功能差异不大但部署更复杂

**配置示例（config.py 新增）：**

```python
# RAG / 向量库
rag_enabled: bool = True
rag_collection_name: str = "laobao_cases"
rag_top_k: int = 5
rag_score_threshold: float = 0.6
rag_persist_dir: str = "./data/vector_store"
embedding_model: str = "BAAI/bge-small-zh-v1.5"
embedding_device: str = "cpu"       # cpu / cuda
embedding_dim: int = 512            # bge-small-zh 输出维度
rerank_enabled: bool = True
rerank_top_k: int = 3
```

### 2.2 Embedding 模型：BAAI/bge-small-zh-v1.5

| 项目 | 值 |
|------|-----|
| **模型** | BAAI/bge-small-zh-v1.5 |
| **参数量** | ~33M |
| **输出维度** | 512 |
| **最大长度** | 512 tokens |
| **语言** | 中文优化 |
| **MTEB 中文排名** | 同类轻量级模型中领先 |

**选择理由：**

1. **轻量快速** — 33M 参数，CPU 上单条文本 embedding 约 10-30ms，适合实时场景
2. **中文优化** — 专门针对中文语义理解训练，在法律文本任务上表现良好
3. **维度适中** — 512 维，比 text-embedding-ada-002（1536 维）存储和计算成本更低
4. **sentence-transformers 兼容** — 一行代码加载，生态成熟
5. **对比其他方案：**
   - `moka-ai/m3e-base`（768 维）：效果相近但模型略大
   - `text2vec-base-chinese`：社区好评但维护不如 BGE 活跃
   - `text-embedding-ada-002`：OpenAI 商业 API，有调用成本和数据隐私风险
   - `shibing624/text2vec-base-chinese`：效果尚可但社区较小

### 2.3 重排序模型：BAAI/bge-reranker-v2-m3

| 项目 | 值 |
|------|-----|
| **模型** | BAAI/bge-reranker-v2-m3 |
| **参数量** | ~568M |
| **用途** | 对检索结果二次精排 |
| **推理方式** | Cross-encoder（成对评分） |

**选择理由：**

1. 向量检索召回 Top-K（如 20 条），重排序精准选出 Top-3，显著提升答案质量
2. 虽然模型较大，但只在检索后调用一次（K=20 约需 1-3 秒），对用户体验影响可控
3. 无需 GPU，CPU 可运行（建议支持 SSE4.2 的 CPU）

### 2.4 额外依赖

**requirements.txt 新增依赖：**

```
# RAG / 向量检索
chromadb>=0.5.0
sentence-transformers>=3.0.0
torch>=2.2.0                    # sentence-transformers 依赖

# 文本预处理
jieba>=0.42.1                   # 中文分词（可选，用于查询改写）
```

**可选（仅数据导入阶段）：**

```
# PDF/Word 案例解析（导入现成案例集）
pdfplumber>=0.11.0
```

**注意：** `sentence-transformers` 会自动下载模型权重到 `~/.cache/huggingface/`，首次启动需要网络连接。模型总大小约 200MB（Embedding + 重排序）。

---

## 3. 案例数据方案

### 3.1 数据来源

| 来源 | 获取方式 | 可用量级 | 更新频率 |
|------|---------|---------|---------|
| **中国裁判文书网**（wenshu.court.gov.cn） | 爬虫 / 公开数据集 | 百万级 | 持续更新 |
| **劳动人事争议典型案例**（人社部发布） | 官网下载 PDF | 每年 30-50 例 | 年度 |
| **最高人民法院公报案例** | 公开获取 | 数百例 | 定期 |
| **各地高院劳动争议白皮书** | 官网 PDF | 每地区 20-50 例 | 年度 |
| **劳动法相关指导案例**（最高人民法院） | 公开获取 | 约 50 例 | 不定期 |

**推荐初始数据源（快速冷启动）：**

1. **第一步（MVP）** — 手动整理 50-100 个典型劳动法案例，涵盖常见场景（辞退、欠薪、加班、工伤、合同、社保、竞业限制）
2. **第二步（扩展）** — 从裁判文书网按关键词筛选劳动纠纷案，清洗后入库 1000-5000 条
3. **第三步（持续）** — 建立定期增量更新机制

### 3.2 数据结构设计

#### Chroma Collection Schema

每条案例作为 Chroma 中的一个 Document，包含：

```python
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class LaborCase:
    """劳动法案例数据结构"""
    # === 必填字段 ===
    case_id: str                    # 唯一 ID，如 "劳仲案-2024-00123"
    case_number: str                # 案号，如 "(2024)陕01民终12345号"
    title: str                      # 案例标题，如 "张三诉XX公司违法解除劳动合同案"
    summary: str                    # 案情摘要（300-500 字），用于向量检索的主文本

    # === 结构化字段 ===
    cause: str                      # 案由，如 "违法解除劳动合同" / "拖欠工资"
    court: str                      # 审理法院
    province: str                   # 省份
    judgment_date: str              # 判决日期 "2024-06-15"
    judgment_result: str            # 判决结果，如 "支持"/"部分支持"/"驳回"
    dispute_focus: List[str]        # 争议焦点列表
    relevant_laws: List[str]        # 相关法条，如 ["劳动合同法第48条"]
    compensation_amount: str        # 赔偿金额（若有），如 "¥86,432.50"
    compensation_detail: str        # 赔偿计算明细

    # === 原文 ===
    full_text: str                  # 判决书全文（用于深度引用）
    source_url: str = ""            # 来源链接
    tags: List[str] = field(default_factory=list)  # 标签

    # === 元数据 ===
    created_at: str = ""            # 入库时间
    updated_at: str = ""            # 更新时间
    active: bool = True             # 是否启用
```

对应 Chroma 的存储映射：

```python
def case_to_chroma_doc(case: LaborCase) -> tuple:
    """将案例转换为 Chroma Document"""
    # 主文本（用于 embedding）
    document = f"{case.title}\n{case.summary}\n"
    document += f"争议焦点: {'; '.join(case.dispute_focus)}\n"
    document += f"判决结果: {case.judgment_result}\n"
    document += f"法律依据: {'; '.join(case.relevant_laws)}"

    # 元数据（用于过滤）
    metadata = {
        "case_id": case.case_id,
        "case_number": case.case_number,
        "cause": case.cause,
        "court": case.court,
        "province": case.province,
        "judgment_date": case.judgment_date,
        "judgment_result": case.judgment_result,
        "compensation_amount": case.compensation_amount,
        "tags": ",".join(case.tags),
    }

    return document, metadata
```

#### SQL 关系表（补充存储，可选）

除了 Chroma，可在现有 SQLite 中增加 `rag_cases` 表，用于存储案例完整信息和便于管理：

```python
# app/models/rag_case.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON
from app.models.base import Base


class RagCase(Base):
    """RAG 案例库 — 存储案例完整信息"""
    __tablename__ = "rag_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String(64), unique=True, nullable=False, index=True)
    case_number = Column(String(100), nullable=False, index=True)
    title = Column(String(300), nullable=False)

    # 结构化字段
    cause = Column(String(100), index=True)          # 案由
    court = Column(String(200))
    province = Column(String(50))
    judgment_date = Column(String(20))
    judgment_result = Column(String(50))             # 支持/部分支持/驳回
    dispute_focus = Column(JSON)                     # 争议焦点列表
    relevant_laws = Column(JSON)                     # 相关法条列表
    compensation_amount = Column(String(50))
    compensation_detail = Column(Text)

    # 内容
    summary = Column(Text, nullable=False)           # 案情摘要
    full_text = Column(Text)                         # 判决书全文
    source_url = Column(String(500))
    tags = Column(String(500))

    # 状态
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### 3.3 预计数据量和存储需求

| 阶段 | 案例数 | Embedding 存储 | 元数据存储 | 总存储 |
|------|--------|---------------|-----------|--------|
| MVP | 50-100 | ~5 MB | ~1 MB | ~10 MB |
| 扩展期 | 1,000-5,000 | ~50 MB | ~10 MB | ~200 MB |
| 成熟期 | 10,000-50,000 | ~500 MB | ~100 MB | ~2 GB |

> **结论：** 即使到 5 万条，SQLite + 本地文件系统即可承载，无需额外数据库。

### 3.4 数据导入流程

```python
# scripts/import_cases.py
"""批量导入案例到 Chroma + SQLite"""

import json
import hashlib
from pathlib import Path
from typing import List

from app.core.config import settings
from app.services.rag_service import rag_service
from app.models.rag_case import RagCase
from app.database import SessionLocal


def import_cases_from_json(json_path: str):
    """从 JSON 文件批量导入案例"""
    with open(json_path, "r", encoding="utf-8") as f:
        cases_data = json.load(f)

    db = SessionLocal()
    try:
        for item in cases_data:
            case = RagCase(
                case_id=_generate_case_id(item),
                case_number=item["case_number"],
                title=item["title"],
                cause=item.get("cause", ""),
                court=item.get("court", ""),
                province=item.get("province", ""),
                judgment_date=item.get("judgment_date", ""),
                judgment_result=item.get("judgment_result", ""),
                dispute_focus=item.get("dispute_focus", []),
                relevant_laws=item.get("relevant_laws", []),
                compensation_amount=item.get("compensation_amount", ""),
                compensation_detail=item.get("compensation_detail", ""),
                summary=item.get("summary", ""),
                full_text=item.get("full_text", ""),
                source_url=item.get("source_url", ""),
                tags=",".join(item.get("tags", [])),
            )
            db.add(case)
            db.commit()

            # 同步到 Chroma
            rag_service.add_case(case)

        print(f"成功导入 {len(cases_data)} 条案例")

    finally:
        db.close()


def _generate_case_id(item: dict) -> str:
    """根据案号生成唯一 ID"""
    raw = item.get("case_number", "")
    hash_str = hashlib.md5(raw.encode()).hexdigest()[:12]
    return f"CASE_{hash_str}"
```

---

## 4. 检索与生成流程

### 4.1 完整流程时序

```
用户提问: "公司违法辞退我，能赔多少钱？"

Step 1 ─ Query 理解
        提取关键要素: 案由=违法辞退, 意图=赔偿计算
        输出: {"cause": "违法解除劳动合同", "intent": "dismissal"}

Step 2 ─ 向量检索（Chroma）
        查询向量: embedding(query)
        相似度检索: collection.query(query_embeddings, n_results=20)
        输出: 20 条候选案例 + 相似度分数

Step 3 ─ 元数据过滤（可选）
        过滤条件: province="陕西"（如果用户咨询陕西）
        输出: 过滤后的候选集

Step 4 ─ 重排序（Cross-encoder）
        输入: query + 20 条候选案例（配对评分）
        输出: 按相关性重新排序的 Top-3 案例
        scores: [0.92, 0.87, 0.76, ...]

Step 5 ─ Prompt 拼接
        System Prompt + 参考案例 + 用户问题
        （详见 4.3 节）

Step 6 ─ AI 生成（DeepSeek）
        流式输出最终答案，实时传回前端
```

### 4.2 核心检索服务

```python
# app/services/rag_service.py
"""RAG 检索服务 — 向量检索 + 重排序 + 上下文拼接"""

import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from app.core.config import settings

logger = logging.getLogger(__name__)


class RAGService:
    """RAG 检索服务"""

    def __init__(self):
        self._embedding_model: Optional[SentenceTransformer] = None
        self._reranker_model: Optional[Any] = None
        self._chroma_client: Optional[chromadb.Client] = None
        self._collection = None
        self._initialized = False

    def initialize(self):
        """初始化所有组件（懒加载）"""
        if self._initialized:
            return

        # 1. 初始化 Embedding 模型
        logger.info(f"加载 Embedding 模型: {settings.embedding_model}")
        self._embedding_model = SentenceTransformer(
            settings.embedding_model,
            device=settings.embedding_device,
        )

        # 2. 初始化重排序模型
        if settings.rerank_enabled:
            logger.info("加载重排序模型: BAAI/bge-reranker-v2-m3")
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
            self._reranker_model = AutoModelForSequenceClassification.from_pretrained(
                "BAAI/bge-reranker-v2-m3"
            )
            self._reranker_tokenizer = AutoTokenizer.from_pretrained(
                "BAAI/bge-reranker-v2-m3"
            )

        # 3. 初始化 Chroma
        persist_dir = Path(settings.rag_persist_dir)
        persist_dir.mkdir(parents=True, exist_ok=True)

        self._chroma_client = chromadb.Client(ChromaSettings(
            persist_directory=str(persist_dir),
            anonymized_telemetry=False,
        ))

        # 4. 获取或创建 Collection
        self._collection = self._chroma_client.get_or_create_collection(
            name=settings.rag_collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        self._initialized = True
        logger.info("RAG 服务初始化完成")

    def _get_embedding(self, text: str) -> List[float]:
        """获取文本 Embedding"""
        if not self._initialized:
            self.initialize()
        return self._embedding_model.encode(text).tolist()

    def retrieve(self, query: str, top_k: int = None) -> Dict[str, Any]:
        """检索相关案例

        Args:
            query: 用户问题
            top_k: 返回结果数

        Returns:
            {
                "reference_cases": [...],   # 用于 prompt 拼接
                "citations": [...],          # 引用来源
            }
        """
        if not self._initialized:
            self.initialize()

        top_k = top_k or settings.rag_top_k
        query_embedding = self._get_embedding(query)

        # Step 1: 向量检索（召回 Top-K * 4 供重排序筛选）
        recall_k = top_k * 4
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=recall_k,
            include=["documents", "metadatas", "distances"],
        )

        if not results["documents"] or not results["documents"][0]:
            return {"reference_cases": [], "citations": []}

        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        # 构建候选列表
        candidates = []
        for i in range(len(documents)):
            candidates.append({
                "document": documents[i],
                "metadata": metadatas[i],
                "score": 1.0 - distances[i],  # cosine distance → similarity
            })

        # Step 2: 重排序
        if settings.rerank_enabled and len(candidates) > top_k:
            candidates = self._rerank(query, candidates)
        else:
            candidates.sort(key=lambda x: x["score"], reverse=True)

        # Step 3: 取 Top-K
        top_cases = candidates[:top_k]

        # Step 4: 构建引用和上下文
        reference_cases = []
        citations = []

        for i, case in enumerate(top_cases):
            meta = case["metadata"]
            ref = {
                "index": i + 1,
                "case_number": meta.get("case_number", ""),
                "cause": meta.get("cause", ""),
                "court": meta.get("court", ""),
                "judgment_date": meta.get("judgment_date", ""),
                "judgment_result": meta.get("judgment_result", ""),
                "summary": case["document"][:300],  # 截取前 300 字摘要
            }
            reference_cases.append(ref)

            citation = {
                "case_number": meta.get("case_number", ""),
                "cause": meta.get("cause", ""),
                "judgment_result": meta.get("judgment_result", ""),
                "relevance_score": round(case["score"], 3),
            }
            citations.append(citation)

        return {
            "reference_cases": reference_cases,
            "citations": citations,
        }

    def _rerank(
        self, query: str, candidates: List[Dict], top_k: int = None
    ) -> List[Dict]:
        """Cross-encoder 重排序"""
        top_k = top_k or settings.rerank_top_k

        pairs = []
        for c in candidates:
            pairs.append([query, c["document"][:512]])  # 截断防止 token 超限

        inputs = self._reranker_tokenizer(
            pairs, padding=True, truncation=True,
            return_tensors="pt", max_length=512,
        )

        with torch.no_grad():
            scores = self._reranker_model(**inputs).logits.squeeze(-1).tolist()

        if not isinstance(scores, list):
            scores = [scores]

        for i, score in enumerate(scores):
            candidates[i]["score"] = score

        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates

    def add_case(self, case: Any):
        """向 Chroma 添加一条案例"""
        if not self._initialized:
            self.initialize()

        # 构建文档文本
        document = f"{case.title}\n{case.summary}\n"
        document += f"争议焦点: {'; '.join(case.dispute_focus)}\n"
        document += f"判决结果: {case.judgment_result}\n"
        document += f"法律依据: {'; '.join(case.relevant_laws)}"

        # 生成 embedding
        embedding = self._get_embedding(document)

        # 元数据
        metadata = {
            "case_id": case.case_id,
            "case_number": case.case_number,
            "cause": case.cause,
            "court": case.court,
            "province": case.province,
            "judgment_date": case.judgment_date,
            "judgment_result": case.judgment_result,
            "compensation_amount": case.compensation_amount,
        }

        self._collection.add(
            embeddings=[embedding],
            documents=[document],
            metadatas=[metadata],
            ids=[case.case_id],
        )
        logger.info(f"案例已加入向量库: {case.case_number}")

    def delete_case(self, case_id: str):
        """从 Chroma 删除一条案例"""
        if not self._initialized:
            self.initialize()
        self._collection.delete(ids=[case_id])
        logger.info(f"案例已从向量库删除: {case_id}")


rag_service = RAGService()
```

### 4.3 参考案例在 Prompt 中的格式设计

修改 `labor_consult.py` 中的 `build_user_prompt`，支持注入参考案例：

```python
def build_user_prompt(
    message: str,
    context: dict = None,
    reference_cases: list = None,
) -> str:
    """构建用户提问 Prompt（含参考案例）"""
    parts = []

    # 如果有参考案例，插入到 prompt 中
    if reference_cases and len(reference_cases) > 0:
        parts.append("【参考案例】")
        for case in reference_cases:
            parts.append(
                f"案例{case['index']}（{case['case_number']}）:\n"
                f"  案由: {case['cause']}\n"
                f"  法院: {case['court']}\n"
                f"  判决结果: {case['judgment_result']}\n"
                f"  摘要: {case['summary']}"
            )
        parts.append("---")

    parts.append(f"用户问题: {message}")

    if context:
        if context.get("city"):
            parts.append(f"城市: {context['city']}")
        if context.get("industry"):
            parts.append(f"行业: {context['industry']}")

    return "\n".join(parts)
```

**System Prompt 新增指令：**

在 `labor_consult.py` 的 `SYSTEM_PROMPT` 中增加：

```
## 参考案例使用规则
1. 回答时必须优先参考上方提供的【参考案例】中的判决结果
2. 引用案例时标注案号，格式为：参考案例（案号），例如"参考(2024)陕01民终12345号"
3. 如果参考案例与用户情况高度相似，可明确指出"根据类案判决结果..."
4. 禁止编造案例信息，仅使用提供的参考案例
5. 如果提供的参考案例均不相关，则基于法律条文回答，并注明"未找到高度相关案例"
```

### 4.4 引用来源标注格式

**API 响应中：**

```json
{
  "session_id": "xxx",
  "message_id": 123,
  "content": "根据相关法律规定...参考(2024)陕01民终12345号...",
  "intent": "dismissal",
  "source": "rag",
  "citations": [
    {
      "case_number": "(2024)陕01民终12345号",
      "cause": "违法解除劳动合同",
      "judgment_result": "支持",
      "relevance_score": 0.923
    },
    {
      "case_number": "(2023)陕01民终6789号",
      "cause": "违法解除劳动合同",
      "judgment_result": "部分支持",
      "relevance_score": 0.871
    }
  ]
}
```

**AI 生成文本中的引用格式：**

```
【一句话结论】
您的案件属于违法解除劳动合同，参考(2024)陕01民终12345号类案判决结果，
公司应支付赔偿金 2N。

【法律依据】
劳动合同法第48条：用人单位违反本法规定解除或者终止劳动合同...
参考案例(2024)陕01民终12345号中，法院支持了劳动者的 2N 赔偿请求。

【赔偿计算】
您的月均工资 8,000 元，工作 3 年 5 个月，
N = 3.5（满1年=1，超过6个月=0.5）
2N = 3.5 × 2 × 8,000 = 56,000 元

【行动建议】
...
```

### 4.5 chat.py 修改示例

```python
# 在 _chat_common 中，FAQ 未命中后新增 RAG 步骤

# ---- 第二步：RAG 检索 ----
reference_cases = []
citations = []

if settings.rag_enabled:
    try:
        rag_result = rag_service.retrieve(user_message)
        reference_cases = rag_result.get("reference_cases", [])
        citations = rag_result.get("citations", [])
    except Exception as e:
        logger.warning(f"RAG 检索失败，回退到纯 AI 生成: {e}")
        reference_cases = []
        citations = []

# ---- 第三步：构建 Prompt（含参考案例） ----
prompt = system_prompt
user_prompt = build_user_prompt_func(
    user_message,
    context={"city": request.city} if hasattr(request, "city") else None,
    reference_cases=reference_cases,
)

# 后续流式输出保持不变，只在最终的 done 事件中添加 citations
```

---

## 5. 实施计划

### 5.1 分阶段实施

#### 第一阶段：基础搭建（1-2 周）

| 任务 | 详情 | 预估工作量 |
|------|------|-----------|
| **环境准备** | 安装 chromadb、sentence-transformers、下载模型 | 0.5 天 |
| **配置更新** | config.py 新增 RAG 相关配置项 | 0.5 天 |
| **RAG 服务实现** | rag_service.py：初始化、检索、添加/删除案例 | 2 天 |
| **Chat 集成** | 修改 chat.py 插入 RAG 步骤 | 1 天 |
| **Prompt 改造** | 修改 labor_consult.py 支持参考案例注入 | 0.5 天 |
| **单元测试** | 测试 rag_service 的增删查改 | 1 天 |

**产出物：**
- `app/services/rag_service.py` — RAG 检索核心服务
- 修改 `app/core/config.py` — 新增 RAG 配置
- 修改 `app/api/v1/chat.py` — 集成 RAG 流程
- 修改 `app/prompts/labor_consult.py` — 支持参考案例

#### 第二阶段：案例数据建设（1-2 周）

| 任务 | 详情 | 预估工作量 |
|------|------|-----------|
| **数据结构设计** | RagCase 模型 + Chroma Schema | 0.5 天 |
| **案例数据采集** | 整理 50-100 个典型劳动法案例（人工 + 半自动） | 3-5 天 |
| **数据导入脚本** | 编写 import_cases.py 批量导入工具 | 1 天 |
| **案例管理 API** | 新增案例增删改查接口 | 1 天 |
| **数据验证** | 验证 Embedding 质量、检索召回率 | 0.5 天 |

**产出物：**
- `app/models/rag_case.py` — 案例数据库模型
- `app/api/v1/rag_cases.py` — 案例管理 API
- `scripts/import_cases.py` — 批量导入脚本
- `data/cases/` — 案例数据目录

#### 第三阶段：效果优化（1 周）

| 任务 | 详情 | 预估工作量 |
|------|------|-----------|
| **重排序集成** | 添加 Cross-encoder 重排序 | 1 天 |
| **查询改写** | 用户问题提取案由、关键词、时间 | 1 天 |
| **元数据过滤** | 按地区、案由、法院层级过滤 | 0.5 天 |
| **AB 测试** | RAG vs 纯 AI 的对比测试 | 1 天 |
| **性能优化** | Embedding 缓存、批量检索 | 0.5 天 |

#### 第四阶段：生产部署（持续）

| 任务 | 详情 |
|------|------|
| 持续收集用户反馈，标注检索质量 |
| 定期更新案例库（随裁判文书网更新） |
| 监控 RAG 检索延迟和准确率 |
| 可选：切换到专用向量库（Milvus/Qdrant）当数据量超 10 万 |

### 5.2 依赖安装和环境准备

**Step 1: 安装 Python 依赖**

```bash
cd /path/to/laobao/backend

# 基础 RAG 依赖
pip install chromadb>=0.5.0 sentence-transformers>=3.0.0

# 如果使用重排序模型
pip install transformers torch

# 案例解析（可选）
pip install pdfplumber python-docx
```

**Step 2: 下载模型（首次自动下载）**

```python
# 测试 Embedding 模型
python -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('BAAI/bge-small-zh-v1.5')
emb = model.encode('测试文本')
print(f'Embedding 维度: {len(emb)}')
"
```

模型将下载到 `~/.cache/huggingface/hub/`，总大小约 200MB。

**Step 3: 配置环境变量**

```bash
# .env 文件新增
RAG_ENABLED=true
RAG_TOP_K=5
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
EMBEDDING_DEVICE=cpu
```

---

## 6. 效果评估

### 6.1 评估指标

| 指标 | 测量方式 | 目标值 | 说明 |
|------|---------|--------|------|
| **检索召回率@K** | 人工标注测试集 100 条 | >85%@K=5 | 前 5 条中包含正确答案 |
| **检索精确率@K** | 人工标注测试集 | >70%@K=5 | 前 5 条中相关案例比例 |
| **MRR**（Mean Reciprocal Rank） | 标准 MRR 计算 | >0.8 | 第一条正确答案的平均排位 |
| **citations 引用准确率** | 人工抽查 AI 输出中的引用 | >95% | AI 引用的案例是否真实存在 |
| **端到端延迟** | 生产监控 | <5s 总响应 | 检索 + 重排序 + 生成 |
| **用户满意度** | 用户反馈按钮 | >80% 好评 | 可在前端加"有用/无用"按钮 |

### 6.2 测试集构建

构建 100 条测试问答对，覆盖以下案由：

| 案由分类 | 测试题数 | 覆盖场景 |
|---------|---------|---------|
| 违法解除劳动合同 | 20 | 孕期辞退、医疗期辞退、试用期辞退等 |
| 拖欠劳动报酬 | 15 | 工资拖欠、提成纠纷、年终奖 |
| 加班费争议 | 15 | 工作日加班、休息日加班、法定假日 |
| 工伤认定与赔偿 | 10 | 工伤认定、伤残赔偿、停工留薪期 |
| 社会保险争议 | 10 | 社保未缴、补缴、损失赔偿 |
| 竞业限制 | 10 | 竞业限制补偿金、违约赔偿 |
| 劳动合同纠纷 | 10 | 双倍工资、合同变更、合同期满 |
| 综合场景 | 10 | 多项请求并存 |

每条测试题格式：

```json
{
  "query": "公司以我业绩不达标为由辞退我，我已经工作3年，能拿多少赔偿？",
  "expected_causes": ["违法解除劳动合同", "经济补偿"],
  "expected_case_numbers": ["(2024)陕01民终12345号"],
  "expected_keywords": ["2N", "赔偿金"],
  "difficulty": "medium"
}
```

### 6.3 冷启动策略

**当案例数据不足时（< 50 条）：**

1. **优先经典案例** — 聚焦每个案由的 3-5 个典型判例，确保基础覆盖
2. **纯 AI 降级** — 在 `rag_service.retrieve()` 中检测：如果检索结果平均分 < 0.5，则 `reference_cases` 置空，回退到纯 AI 生成
3. **混合模式** — 即使案例少也尝试提供引用，避免用户对无引用回答产生不信任
4. **快速标注工具** — 提供一个简单的 Web 界面，让运营人员快速标注案例与问题匹配度

**降级逻辑代码示例：**

```python
def retrieve(self, query: str) -> Dict[str, Any]:
    """带冷启动降级的检索"""
    results = self._raw_retrieve(query)

    # 冷启动检测：平均分低于阈值则降级
    if results["reference_cases"]:
        avg_score = sum(
            c["relevance_score"] for c in results["reference_cases"]
        ) / len(results["reference_cases"])

        if avg_score < settings.rag_score_threshold:
            logger.info(f"RAG 质量不足 (avg={avg_score:.2f}), 降级到纯 AI")
            return {"reference_cases": [], "citations": []}

    return results
```

### 6.4 持续改进

1. **用户反馈闭环** — 前端添加"这个引用有用吗？"按钮，记录 feedback 到数据库
2. **定期评估** — 每月用测试集跑一遍，跟踪检索准确率变化
3. **案例增量更新** — 每次新增案例后重新评估 Top-K 召回率
4. **嵌入模型升级** — 当更好的中文 Embedding 模型出现时，可重新生成所有案例的 Embedding

---

## 7. 附录：完整代码清单

### 7.1 新增文件

```
backend/
├── app/
│   ├── api/v1/
│   │   └── rag_cases.py          # 案例管理 API
│   ├── models/
│   │   └── rag_case.py            # 案例数据模型
│   └── services/
│       └── rag_service.py         # RAG 检索服务
├── data/
│   ├── vector_store/              # Chroma 持久化目录（gitignore）
│   └── cases/                     # 案例数据（JSON）
│       └── seed_cases.json        # 初始种子案例
└── scripts/
    └── import_cases.py            # 批量导入脚本
```

### 7.2 修改文件

```
backend/
├── app/
│   ├── api/v1/
│   │   ├── chat.py                # 新增 RAG 步骤
│   │   └── router.py              # 注册 rag_cases 路由
│   ├── core/
│   │   └── config.py              # 新增 RAG 配置项
│   └── prompts/
│       └── labor_consult.py       # 支持参考案例注入
└── requirements.txt               # 新增依赖
```

### 7.3 案例管理 API

```python
# app/api/v1/rag_cases.py
"""RAG 案例库管理接口"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.common import APIResponse
from app.models.rag_case import RagCase
from app.services.rag_service import rag_service

router = APIRouter(tags=["rag_cases"])


@router.get("/rag/cases")
def list_cases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    cause: str = Query("", description="按案由筛选"),
    db: Session = Depends(get_db),
):
    """案例列表"""
    query = db.query(RagCase).filter(RagCase.is_active.is_(True))

    if cause:
        query = query.filter(RagCase.cause == cause)

    total = query.count()
    items = query.order_by(RagCase.created_at.desc())\
                 .offset((page - 1) * page_size)\
                 .limit(page_size)\
                 .all()

    return APIResponse(data={
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": [
            {
                "case_id": c.case_id,
                "case_number": c.case_number,
                "title": c.title,
                "cause": c.cause,
                "court": c.court,
                "judgment_date": c.judgment_date,
                "judgment_result": c.judgment_result,
                "tags": c.tags.split(",") if c.tags else [],
            }
            for c in items
        ],
    })


@router.post("/rag/cases/sync")
def sync_case(case_id: str = Query(...), db: Session = Depends(get_db)):
    """将一条数据库中的案例同步到 Chroma"""
    case = db.query(RagCase).filter(RagCase.case_id == case_id).first()
    if not case:
        return APIResponse(code=404, data=None, message="案例未找到")

    rag_service.add_case(case)
    return APIResponse(data={"case_id": case_id, "status": "synced"})


@router.post("/rag/cases/sync-all")
def sync_all_cases(db: Session = Depends(get_db)):
    """将所有活跃案例同步到 Chroma"""
    cases = db.query(RagCase).filter(RagCase.is_active.is_(True)).all()
    for case in cases:
        rag_service.add_case(case)
    return APIResponse(data={"total": len(cases), "status": "synced"})
```

### 7.4 router.py 注册

```python
# app/api/v1/router.py
from app.api.v1 import health, chat, knowledge, calculator, document, template, contract_scan, rag_cases

router = APIRouter(prefix="/api/v1")
# ... 已有路由 ...
router.include_router(rag_cases.router)
```

### 7.5 完整的 config.py 更新

```python
# app/core/config.py
"""应用配置 — 从 .env 读取"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # AI
    ai_api_key: str = ""
    ai_base_url: str = "http://127.0.0.1:8084"
    ai_model: str = "deepseek-v4-pro"
    ai_max_tokens: int = 4096
    ai_temperature: float = 0.3

    # 数据库
    database_url: str = "sqlite:///./data/app.db"

    # 服务
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    log_level: str = "INFO"

    # === RAG 向量检索 ===
    rag_enabled: bool = True
    rag_collection_name: str = "laobao_cases"
    rag_top_k: int = 5
    rag_score_threshold: float = 0.6
    rag_persist_dir: str = "./data/vector_store"

    # Embedding 模型
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_device: str = "cpu"
    embedding_dim: int = 512

    # 重排序
    rerank_enabled: bool = True
    rerank_top_k: int = 3

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
```

---

## 附录：为何选择 Chroma 而非其他方案

| 维度 | Chroma | Milvus | FAISS | Pinecone |
|------|--------|--------|-------|----------|
| **部署复杂度** | 零（嵌入式） | 需要 Docker | 需要自行管理 | SaaS |
| **数据持久化** | 内建（DuckDB） | 需 etcd/MinIO | 需自行实现 | 托管 |
| **运维成本** | 几乎为零 | 高 | 中 | 低 |
| **检索速度（万级）** | <100ms | <10ms | <10ms | <50ms |
| **适合当前规模** | 是 | 过度设计 | 不完整 | 有费用 |

**最终建议：** 以 Chroma 起步，当案例数超过 10 万条或需要分布式部署时，再平滑迁移到 Milvus。

---

> **本方案为 驷马用工宝 RAG 案例库建设提供完整的技术指引，实施时应先从第一阶段开始，逐步迭代上线。**
