# Study Helper 学习助手

AI驱动的面试题练习系统，支持问题提取、答案生成、智能练习、AI评分等功能。

## 🚀 快速启动

### 方法一：一键启动（推荐）
1. 双击 `start_backend.bat` 启动后端服务
2. 双击 `start_frontend.bat` 启动前端（或直接打开 `web/index.html`）
3. （可选）双击 `start_auto_process.bat` 启动自动处理服务
4. 在浏览器访问 http://localhost:3000 开始使用

### 方法二：命令行启动
```bash
# 1. 启动后端
cd backend
python main.py

# 2. 打开前端（任选一种）
# 方式A：直接在浏览器打开 web/index.html
# 方式B：启动本地服务器
cd web
python -m http.server 3000
```

## 项目结构

```
studyHelper/
├── backend/                 # FastAPI后端
│   ├── app/
│   │   ├── routers/        # API路由（source, questions, practice）
│   │   ├── models.py       # SQLAlchemy数据模型
│   │   ├── schemas.py      # Pydantic数据验证
│   │   └── database.py     # 数据库连接
│   ├── main.py             # FastAPI应用入口
│   └── requirements.txt    # Python依赖
│
├── web/                    # 前端界面
│   └── index.html          # 单页应用（Alpine.js + Tailwind CSS）
│
├── questionExtract/        # 问题提取工具包
│   ├── config.py                  # 配置文件（数据库、API密钥）
│   ├── question_parser.py         # 问题解析器
│   ├── answer_generator.py        # 答案生成器
│   ├── process_questions.py       # 批量处理脚本
│   ├── generate_answers.py        # 答案生成脚本
│   ├── migrate_add_tables.py      # 数据库迁移
│   └── README.md                  # 详细文档
│
├── baseFiles/              # 数据文件目录
│   └── interviewQuestions.xlsx   # Excel数据源
│
├── start_backend.bat       # 后端启动脚本
├── start_frontend.bat      # 前端启动脚本
├── test_api.py             # API测试脚本
├── WEB_APP_README.md       # Web应用详细文档
└── README.md               # 本文档（项目总览）
```

## 主要功能

### 📝 1. 问题管理系统
- **Excel导入**: 从Excel批量导入原始问题
- **AI提取**: 使用Qwen自动识别和拆分明细问题
- **答案生成**: AI自动生成答案、关键词和领域分类
- **原始问题管理**: Web界面手动添加和管理原始问题

### 🎯 2. 智能练习系统
- **随机出题**: 支持按领域、掌握程度、是否有答案筛选
- **AI评分**: 使用Qwen对用户回答进行多维度评分（0-100分）
  - 准确性：回答是否准确、正确
  - 完整性：是否涵盖关键要点
  - 深度：回答的深度和理解程度
  - 表达：逻辑性和条理性
- **掌握程度**: 三级标记（不会 / 一般 / 会了）
- **练习记录**: 完整记录每次练习的答案、评分、耗时

### 📊 3. 数据统计分析
- 问题总数、已有答案数量统计
- 练习次数和掌握情况分析
- 按掌握程度筛选复习

### 🏗️ 4. Web应用
- **后端**: FastAPI + SQLAlchemy + PostgreSQL
- **前端**: 响应式单页应用（Alpine.js + Tailwind CSS）
- **RESTful API**: 完整的API文档（Swagger + ReDoc）

详细文档：[WEB_APP_README.md](WEB_APP_README.md)

### 🤖 5. 自动处理服务
- **后台监控**: 每5分钟自动检查未处理的原始问题
- **全自动流程**: 提取 → 改写 → 生成答案，无需手动操作
- **手机添加**: 在手机上添加问题，电脑后台自动处理
- **Windows任务**: 支持开机自启，完全自动化

详细文档：[AUTO_PROCESS_GUIDE.md](AUTO_PROCESS_GUIDE.md)

### 💼 6. 岗位分析系统（RAG核心功能）
- **智能JD分析**: AI自动分析岗位要求和核心技能
- **RAG知识检索**: 基于向量数据库检索相关题目和笔记
- **个性化推荐**: 推荐针对性练习题目
- **准备计划生成**: 自动生成详细的面试准备计划
- **知识库整合**: 整合所有题目、笔记、历史岗位信息

详细架构见下方"RAG技术架构"章节

## 技术栈

### 后端
- **Python**: 3.12+
- **Web框架**: FastAPI
- **ORM**: SQLAlchemy
- **数据库**: PostgreSQL
- **数据处理**: pandas, openpyxl
- **AI SDK**: OpenAI SDK (for Qwen API)

### RAG技术栈
- **Embedding模型**: sentence-transformers (paraphrase-multilingual-MiniLM-L12-v2)
- **向量数据库**: ChromaDB (持久化存储)
- **中文分词**: jieba
- **重排序算法**: BM25 (rank-bm25)
- **大语言模型**: Qwen-Plus (通义千问)

### 前端
- **核心**: HTML5 + JavaScript
- **CSS框架**: Tailwind CSS
- **响应式框架**: Alpine.js
- **HTTP客户端**: Fetch API

### AI模型
- **服务商**: 阿里云通义千问
- **模型**: Qwen-Plus
- **用途**: 问题提取、答案生成、智能评分

## RAG技术架构详解

### 完整流程图

```
┌─────────────────────────────────────────────────────────────┐
│  岗位分析RAG完整流程                                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [1] 知识库构建 (Knowledge Base Construction)              │
│      ├── 数据源采集                                         │
│      │   ├─ 所有题目 (refined_question + answer)          │
│      │   ├─ 笔记内容 (interview_notes.content)            │
│      │   └─ 历史岗位分析 (job_analyses.jd_content)        │
│      │                                                       │
│      ├── 文本向量化 (Embedding)                            │
│      │   ├─ 模型: paraphrase-multilingual-MiniLM-L12-v2   │
│      │   ├─ 维度: 384维向量                                │
│      │   └─ 语言: 支持中英文多语言                         │
│      │                                                       │
│      └── 向量存储 (Vector Storage)                         │
│          ├─ 数据库: ChromaDB (持久化)                      │
│          ├─ 路径: backend/chroma_db/                       │
│          └─ 集合: interview_knowledge                      │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [2] 语义检索 (Semantic Search)                            │
│      ├── 查询向量化                                         │
│      │   └─ 将岗位JD转为384维向量                          │
│      │                                                       │
│      ├── 向量相似度计算                                     │
│      │   ├─ 算法: 余弦相似度 (Cosine Similarity)           │
│      │   ├─ 召回数: Top 20                                  │
│      │   └─ 返回: 最相关的20条知识                         │
│      │                                                       │
│      └── 初步结果集                                         │
│          └─ 20条语义相关的题目/笔记/岗位                   │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [3] BM25重排序 (BM25 Reranking)                           │
│      ├── 中文分词                                           │
│      │   ├─ 工具: jieba分词                                │
│      │   └─ 对查询和候选文档进行分词                       │
│      │                                                       │
│      ├── 关键词匹配评分                                     │
│      │   ├─ 算法: BM25Okapi                                │
│      │   ├─ 参数: k1=1.5, b=0.75                           │
│      │   └─ 评分: 基于词频和逆文档频率                     │
│      │                                                       │
│      └── 精排结果                                           │
│          ├─ 重排序: 按BM25分数排序                         │
│          ├─ 精选: Top 10                                    │
│          └─ 返回: 最终相关的10条知识                       │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [4] 上下文聚合 (Context Aggregation)                      │
│      ├── 知识整合                                           │
│      │   ├─ 相关题目: 题目+答案+关键词                     │
│      │   ├─ 笔记心得: 面试经验和学习心得                   │
│      │   └─ 历史岗位: 过往分析的岗位要求                   │
│      │                                                       │
│      └── Prompt构建                                         │
│          ├─ 岗位JD                                          │
│          ├─ 检索到的相关知识                               │
│          └─ 任务指令 (生成面试准备计划)                    │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [5] 大模型生成 (LLM Generation)                           │
│      ├── 模型调用                                           │
│      │   ├─ 模型: Qwen-Plus                                │
│      │   ├─ 温度: 0.7 (平衡创造性和准确性)                 │
│      │   └─ 最大token: 4000                                │
│      │                                                       │
│      ├── 生成内容                                           │
│      │   ├─ 岗位分析 (核心技能、考察方向)                  │
│      │   ├─ 准备策略 (技术准备、项目经验)                  │
│      │   ├─ 学习路径 (必须掌握、需要复习、加分项)          │
│      │   ├─ 模拟问题 (5-10个可能的面试问题)               │
│      │   └─ 时间规划 (准备周期、每日安排)                  │
│      │                                                       │
│      └── 推荐题目                                           │
│          └─ 从检索结果中提取题目ID列表                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 核心技术实现

#### 1. Embedding向量化

**模型选择**: `paraphrase-multilingual-MiniLM-L12-v2`
- **优势**: 支持中英文，模型较小(约500MB)，速度快
- **输出**: 384维密集向量
- **用途**: 将文本转换为高维空间中的点，语义相似的文本距离更近

**实现代码** (rag_service.py):
```python
from sentence_transformers import SentenceTransformer

self.embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
embeddings = self.embedding_model.encode(documents)
```

#### 2. ChromaDB向量数据库

**特性**:
- 持久化存储，重启后数据不丢失
- 自动计算余弦相似度
- 支持元数据过滤

**实现代码**:
```python
import chromadb

self.chroma_client = chromadb.PersistentClient(path="./chroma_db")
self.collection = self.chroma_client.get_or_create_collection("interview_knowledge")

# 存储向量
self.collection.add(
    documents=documents,
    embeddings=embeddings.tolist(),
    metadatas=metadatas,
    ids=ids
)

# 语义检索
results = self.collection.query(
    query_embeddings=[query_embedding.tolist()],
    n_results=20
)
```

#### 3. BM25重排序算法

**算法原理**:
- TF (词频): 词在文档中出现的频率
- IDF (逆文档频率): 词的稀有程度
- 文档长度归一化: 避免长文档优势

**实现代码**:
```python
from rank_bm25 import BM25Okapi
import jieba

# 中文分词
query_tokens = list(jieba.cut(query))
corpus_tokens = [list(jieba.cut(doc['document'])) for doc in candidates]

# BM25评分
bm25 = BM25Okapi(corpus_tokens)
scores = bm25.get_scores(query_tokens)

# 重排序
sorted_results = sorted(zip(candidates, scores), key=lambda x: x[1], reverse=True)
```

#### 4. 混合检索策略

**为什么需要混合检索?**
- **向量检索**: 捕捉语义相似性，但可能忽略关键词精确匹配
- **BM25检索**: 关键词匹配准确，但无法理解语义

**组合策略**:
1. 先用向量检索召回Top 20 (召回率优先)
2. 再用BM25重排序选Top 10 (精确度优先)
3. 结合两者优势，提升检索质量

### 性能指标

| 操作 | 耗时 | 说明 |
|------|------|------|
| 知识库构建 | 5-10秒 | 100条记录，首次需下载模型 |
| 向量检索 | <1秒 | ChromaDB高效查询 |
| BM25重排 | <0.5秒 | 本地计算，速度快 |
| LLM生成 | 30-60秒 | 取决于网络和API响应 |
| **总耗时** | **35-70秒** | 完整RAG流程 |

### 知识库数据流

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ PostgreSQL   │────>│ RAG Service  │────>│  ChromaDB    │
│ (关系数据库) │     │ (向量化)     │     │ (向量数据库) │
└──────────────┘     └──────────────┘     └──────────────┘
      │                                           │
      │ 读取                                      │ 存储
      ▼                                           ▼
 - 题目+答案                                  - 384维向量
 - 笔记内容                                  - 元数据(类型、ID)
 - 岗位JD                                    - 文档内容

                    查询时 ↓

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ 用户输入JD   │────>│ Embedding    │────>│ 向量相似度   │
└──────────────┘     │ 向量化       │     │ Top 20召回   │
                    └──────────────┘     └──────────────┘
                                                 │
                                                 ▼
                    ┌──────────────┐     ┌──────────────┐
                    │ Qwen LLM     │<────│ BM25重排序   │
                    │ 生成计划     │     │ Top 10精排   │
                    └──────────────┘     └──────────────┘
```

### 关键代码路径

- **RAG服务**: `backend/app/services/rag_service.py` (完整RAG实现)
- **岗位分析API**: `backend/app/routers/job_analysis.py` (调用RAG服务)
- **向量数据库**: `backend/chroma_db/` (ChromaDB持久化存储)
- **依赖安装**: `install_rag_deps.bat` (一键安装RAG依赖)

### 首次使用注意

1. **安装RAG依赖** (必须):
   ```bash
   install_rag_deps.bat
   ```
   首次会下载约500MB的Embedding模型，需要耐心等待。

2. **模型缓存位置**:
   - Windows: `C:\Users\<用户名>\.cache\torch\sentence_transformers\`
   - 下载一次后，后续使用无需重新下载

3. **向量数据库更新**:
   - 每次执行岗位分析时，自动重建最新知识库
   - 新增题目/笔记会自动纳入检索范围

## 环境配置

### 数据库配置

项目使用PostgreSQL数据库，配置信息在各模块的 `config.py` 中：

```python
DATABASE_URL = "postgresql://postgres:TMPpassword1@localhost:5432/postgres"
```

### API密钥配置

需要在 `questionExtract/config.py` 中配置Qwen API密钥：

```python
QWEN_API_KEY = "your-api-key"
```

## 使用流程

### 首次使用

1. **安装依赖**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. **数据库迁移**（如果是首次使用）
   ```bash
   cd questionExtract
   python migrate_add_tables.py
   ```

3. **导入问题**（可选，如果有Excel数据）
   ```bash
   cd questionExtract
   python process_questions.py
   ```

4. **生成答案**（可选）
   ```bash
   cd questionExtract
   python generate_answers.py --max 50
   ```

5. **启动系统**
   - 双击 `start_backend.bat`
   - 双击 `start_frontend.bat` 或直接打开 `web/index.html`

### 日常使用

1. 启动后端和前端
2. 在Web界面选择"练习模式"
3. 点击"随机出题"
4. 回答问题并提交
5. 查看AI评分和反馈
6. 继续下一题

### 测试API

```bash
python test_api.py
```

## 开发计划

- [x] 问题提取功能（从Excel导入）
- [x] AI答案生成和领域分类
- [x] Web后端API（FastAPI）
- [x] Web前端界面（单页应用）
- [x] 智能练习系统
- [x] AI评分系统
- [ ] 用户登录系统
- [ ] 学习报告导出
- [ ] 学习曲线图表
- [ ] 移动端适配
- [ ] 错题本功能
- [ ] 定时复习提醒

## 常见问题

### Q: 如何测试后端是否正常？
运行测试脚本：
```bash
python test_api.py
```
如果看到所有测试通过（✓），说明后端工作正常。

### Q: 前端无法连接后端怎么办？
1. 确认后端已启动
2. 访问 http://localhost:8000/health 应返回 `{"status": "healthy"}`
3. 如果使用代理，设置环境变量：`set NO_PROXY=localhost,127.0.0.1`
4. 检查浏览器控制台是否有CORS错误

### Q: 如何修改端口？
在 `backend/main.py` 最后一行修改端口号（默认8000）。

### Q: 如何批量导入问题？
使用Excel导入：
```bash
cd questionExtract
python process_questions.py
```

### Q: 领域分类有哪些？
系统支持8个领域的自动分类：
- 大模型
- RAG
- 记忆管理
- Langchain语法
- 智能体框架
- 效果评测
- 工程化部署实践
- 其他

## 注意事项

1. **数据库**: 确保PostgreSQL已启动并可访问
2. **API密钥**: Qwen API需要有足够的调用额度
3. **Python版本**: 建议 3.12+
4. **代理问题**: 如果使用代理，需设置 `NO_PROXY=localhost,127.0.0.1`
5. **安全**: 不要将API密钥和数据库密码提交到版本控制

## 文档

- [项目总览](README.md) - 本文档
- [Web应用详细文档](WEB_APP_README.md) - 完整API文档、数据库说明、使用流程
- [问题提取模块](questionExtract/README.md) - questionExtract模块详细说明

## 版本信息

- **版本**: 1.0.0
- **更新时间**: 2025-12-30
- **开发工具**: Claude Code + Qwen AI

## 许可证

仅供个人学习使用。
