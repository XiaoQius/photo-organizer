"""AI 场景打标：调用 OpenAI 兼容视觉接口，为照片批量生成中文标签（可选功能）。"""

import base64
import json
import os

import httpx
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.media import MediaFile
from app.services import jobs
from app.services.thumbnail import get_thumbnail

PROMPT = (
    "你是照片整理助手。下面是多张照片的缩略图，按顺序编号。"
    "请为每张照片输出2-4个简短中文场景标签（如：人物/风景/美食/宠物/建筑/夜景/证件/"
    "文档/自拍/聚会/运动/旅行/花草/天空/街拍/海洋/雪景/儿童）。"
    '只返回 JSON 数组，格式：[{"index":1,"tags":["风景","日落"]}]，不要其他文字。'
)


def llm_config() -> dict:
    return {
        "api_key": os.getenv("LLM_API_KEY", ""),
        "base_url": os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
    }


def is_configured() -> bool:
    return bool(llm_config()["api_key"])


def start_tagging(max_images: int = 200) -> str:
    if not is_configured():
        raise ValueError("未配置 LLM API，请先设置环境变量 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL")
    return jobs.start_job("ai_tag", lambda job: _tag_worker(job, max_images), label=f"最多 {max_images} 张")


def _tag_worker(job: dict, max_images: int) -> dict:
    db = SessionLocal()
    tagged = 0
    try:
        files = (db.query(MediaFile)
                 .filter(MediaFile.status == "active", MediaFile.media_type == "photo")
                 .order_by(MediaFile.taken_at.desc().nullslast())
                 .limit(max_images).all())
        job["total"] = len(files)
        cfg = llm_config()
        batch_size = 4
        for i in range(0, len(files), batch_size):
            if job["status"] == "cancelled":
                break
            batch = files[i:i + batch_size]
            content: list[dict] = [{"type": "text", "text": PROMPT}]
            valid: list[MediaFile] = []
            for m in batch:
                thumb = get_thumbnail(m.path, m.media_type, m.mtime)
                if not thumb:
                    continue
                b64 = base64.b64encode(thumb.read_bytes()).decode()
                content.append({"type": "text", "text": f"第 {len(valid) + 1} 张（ID {m.id}）："})
                content.append({"type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
                valid.append(m)
            if not valid:
                continue
            job["current"] = f"正在识别 {len(valid)} 张照片"
            tags_by_index = _call_llm(cfg, content, len(valid))
            for idx, m in enumerate(valid):
                tags = tags_by_index.get(idx + 1)
                if tags:
                    existing = set(m.tags or [])
                    m.tags = sorted(existing | set(tags))
                    tagged += 1
            db.commit()
            job["processed"] = min(i + batch_size, len(files))
        return {"tagged": tagged}
    finally:
        db.close()


def _call_llm(cfg: dict, content: list[dict], count: int) -> dict[int, list[str]]:
    body = {
        "model": cfg["model"],
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 500,
        "temperature": 0.2,
    }
    resp = httpx.post(f"{cfg['base_url']}/chat/completions", json=body,
                      headers={"Authorization": f"Bearer {cfg['api_key']}"},
                      timeout=120)
    resp.raise_for_status()
    text = resp.json()["choices"][0]["message"]["content"]
    # 容错解析：截取第一个 JSON 数组
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        return {}
    try:
        items = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}
    result: dict[int, list[str]] = {}
    for item in items:
        if isinstance(item, dict) and "index" in item and isinstance(item.get("tags"), list):
            idx = int(item["index"])
            if 1 <= idx <= count:
                result[idx] = [str(t) for t in item["tags"]][:4]
    return result
