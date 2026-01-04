"""
FastAPI主应用
"""
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.routers import source, questions, practice, notes, schedules, job_analysis, chat, evaluation
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="面试题练习系统API",
    description="支持问题管理、随机练习、AI评分等功能",
    version="1.0.0"
)

# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """记录所有HTTP请求和响应"""
    start_time = time.time()

    # 记录请求信息
    logger.info(f"→ {request.method} {request.url.path} from {request.client.host}")
    if request.query_params:
        logger.info(f"  Query params: {dict(request.query_params)}")

    # 处理请求
    response = await call_next(request)

    # 计算处理时间
    duration = time.time() - start_time

    # 记录响应信息
    status_emoji = "✓" if response.status_code < 400 else "✗"
    logger.info(f"← {request.method} {request.url.path} - {response.status_code} {status_emoji} ({duration:.3f}s)")

    return response


# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该指定具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(source.router, prefix="/api")
app.include_router(questions.router, prefix="/api")
app.include_router(practice.router, prefix="/api")
app.include_router(notes.router, prefix="/api")
app.include_router(schedules.router, prefix="/api")
app.include_router(job_analysis.router, prefix="/api")
app.include_router(chat.router, prefix="/api")  # Chatbot API
app.include_router(evaluation.router, prefix="/api")  # Evaluation & A/B Testing


@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    logger.info("=" * 80)
    logger.info("面试题练习系统API - 启动成功")
    logger.info("=" * 80)
    logger.info("API文档: http://localhost:8000/docs")
    logger.info("健康检查: http://localhost:8000/health")
    logger.info("=" * 80)


@app.get("/")
def root():
    """根路径"""
    return {
        "message": "面试题练习系统API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
def health_check():
    """健康检查"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    import os

    # 从环境变量读取是否使用reload模式，默认为True
    use_reload = os.getenv("RELOAD", "true").lower() == "true"

    logger.info(f"启动模式: {'热重载' if use_reload else '普通模式'}")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=use_reload)
