"""整理计划：模板化路径、可编辑计划、执行、撤销与 CSV 导出。"""

import csv
import io
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.media import MediaFile
from app.models.organize_log import OrganizeLog
from app.services.classify import CATEGORY_LABELS

# plan_id -> {"created_at": ts, "params": {...}, "items": [ {...}, ... ]}
_plans: dict[str, dict] = {}

# 目录模板支持：{year} {month} {day} {city} {category} {type}
# 文件名模板支持：{prefix} {datetime} {original}
FOLDER_TOKENS = ["{year}", "{month}", "{day}", "{city}", "{category}", "{type}"]
NAME_TOKENS = ["{prefix}", "{datetime}", "{original}"]

DEFAULT_FOLDER_TEMPLATE = "{year}/{month}"
DEFAULT_NAME_TEMPLATE = "{prefix}_{datetime}"

# 预设：前端 Segmented 选项 → 模板字符串
FOLDER_PRESETS = {
    "Y/M": "{year}/{month}",
    "Y/M/D": "{year}/{month}/{day}",
    "Y/M/CITY": "{year}/{month}/{city}",
    "Y/CITY": "{year}/{city}",
    "Y/TYPE/M": "{type}/{year}/{month}",
}
NAME_PRESETS = {"standard": "{prefix}_{datetime}", "keep": "{original}"}


def _sanitize_part(value: str) -> str:
    for ch in '\\/:*?"<>|':
        value = value.replace(ch, "")
    return value.strip() or "未命名"


def _render_folder(template: str, m: MediaFile, taken: datetime) -> str:
    from app.config import TYPE_LABELS
    type_label = TYPE_LABELS.get(m.media_type, m.media_type)
    category = CATEGORY_LABELS.get(m.category, type_label) if m.media_type == "photo" else type_label
    parts = []
    for raw in template.replace("\\", "/").split("/"):
        part = (raw.replace("{year}", f"{taken.year:04d}")
                .replace("{month}", f"{taken.month:02d}")
                .replace("{day}", f"{taken.day:02d}")
                .replace("{city}", m.city or "未知地点")
                .replace("{category}", category)
                .replace("{type}", type_label))
        if "{" in part:
            continue  # 未知 token 整段丢弃，避免产生 "{xxx}" 文件夹
        parts.append(_sanitize_part(part))
    return "/".join(parts) or f"{taken.year:04d}"


def _render_name(template: str, m: MediaFile, taken: datetime) -> str:
    from app.config import TYPE_PREFIXES
    prefix = TYPE_PREFIXES.get(m.media_type, "FILE")
    name = (template.replace("{prefix}", prefix)
            .replace("{datetime}", taken.strftime("%Y%m%d_%H%M%S"))
            .replace("{original}", Path(m.filename).stem))
    name = _sanitize_part(name)
    ext = m.ext.lower()
    if ext in {".jpeg", ".tif", ".heif"}:
        ext = {".jpeg": ".jpg", ".tif": ".tiff", ".heif": ".heic"}[ext]
    return f"{name}{ext}"


def resolve_templates(folder_structure: str, naming: str,
                      folder_template: str, name_template: str) -> tuple[str, str]:
    """预设值与自定义模板统一解析成最终模板。"""
    folder = (folder_template or "").strip() or FOLDER_PRESETS.get(folder_structure, DEFAULT_FOLDER_TEMPLATE)
    name = (name_template or "").strip() or NAME_PRESETS.get(naming, DEFAULT_NAME_TEMPLATE)
    return folder.replace("\\", "/"), name


def build_plan(db: Session, media_ids: list[int], target_dir: str, mode: str,
               folder_structure: str, naming: str,
               folder_template: str = "", name_template: str = "") -> str:
    """生成整理计划，返回 plan_id。mode: move / copy。"""
    target = Path(target_dir)
    folder_tpl, name_tpl = resolve_templates(folder_structure, naming, folder_template, name_template)
    items: list[dict] = []
    used_dst: set[str] = set()

    query = db.query(MediaFile).filter(MediaFile.status == "active")
    if media_ids:
        query = query.filter(MediaFile.id.in_(media_ids))
    files = query.order_by(MediaFile.taken_at.asc().nullslast(), MediaFile.filename.asc()).all()

    for m in files:
        taken = m.taken_at or datetime.fromtimestamp(m.mtime)
        rel_dir = _render_folder(folder_tpl, m, taken)
        dst_dir = target / Path(*rel_dir.split("/"))
        candidate = dst_dir / _render_name(name_tpl, m, taken)
        note = ""
        action = mode
        # 冲突处理：目标已存在相同内容则跳过，否则加序号
        seq = 0
        while True:
            existing_md5 = _md5_of(str(candidate)) if candidate.exists() else None
            if not candidate.exists():
                break
            if existing_md5 and m.md5 and existing_md5 == m.md5:
                action, note = "skip", "目标已存在相同文件"
                break
            seq += 1
            stem, ext = candidate.stem, candidate.suffix
            candidate = dst_dir / f"{stem}_{seq}{ext}"
        # 同一计划内避免重复目标
        while str(candidate).lower() in used_dst and action != "skip":
            seq += 1
            stem, ext = candidate.stem, candidate.suffix
            candidate = dst_dir / f"{stem}_{seq}{ext}"
        if action != "skip":
            used_dst.add(str(candidate).lower())

        items.append({
            "media_id": m.id,
            "filename": m.filename,
            "media_type": m.media_type,
            "src": m.path,
            "dst": str(candidate),
            "dst_dir": str(dst_dir),
            "action": action,
            "note": note,
            "size": m.size,
            "excluded": False,
        })

    plan_id = uuid.uuid4().hex[:12]
    _plans[plan_id] = {
        "created_at": datetime.now().timestamp(),
        "params": {"target_dir": target_dir, "mode": mode,
                   "folder_structure": folder_structure, "naming": naming,
                   "folder_template": folder_tpl, "name_template": name_tpl},
        "items": items,
    }
    # 只保留最近 3 个计划
    if len(_plans) > 3:
        for old_id in sorted(_plans, key=lambda k: _plans[k]["created_at"])[:-3]:
            del _plans[old_id]
    return plan_id


def get_plan(plan_id: str) -> dict | None:
    plan = _plans.get(plan_id)
    return dict(plan) if plan else None


def update_plan_items(plan_id: str, excluded_ids: list[int] | None = None,
                      dst_overrides: dict[int, str] | None = None) -> dict | None:
    """编辑计划：勾选/取消排除文件，覆盖单个文件的目标路径。"""
    plan = _plans.get(plan_id)
    if not plan:
        return None
    excluded = set(excluded_ids or [])
    overrides = dst_overrides or {}
    for item in plan["items"]:
        item["excluded"] = item["media_id"] in excluded
        if item["media_id"] in overrides:
            dst = overrides[item["media_id"]].strip()
            if dst:
                item["dst"] = str(Path(dst))
                item["dst_dir"] = str(Path(dst).parent)
    return plan


def execute_plan(db: Session, plan_id: str) -> dict:
    """执行整理计划（跳过排除项），返回结果摘要并写入日志。"""
    plan = _plans.get(plan_id)
    if not plan:
        raise ValueError("计划不存在或已过期，请重新生成")
    batch_id = uuid.uuid4().hex[:12]
    done = failed = skipped = 0
    for item in plan["items"]:
        if item.get("excluded"):
            continue
        src, dst, action = item["src"], item["dst"], item["action"]
        log = OrganizeLog(batch_id=batch_id, media_file_id=item["media_id"],
                          src_path=src, dst_path=dst, action=action, message=item.get("note", ""))
        if action == "skip":
            log.status = "skipped"
            skipped += 1
            db.add(log)
            continue
        try:
            dst_path = Path(dst)
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            if action == "move":
                shutil.move(src, dst_path)
                m = db.get(MediaFile, item["media_id"])
                if m:
                    m.path = str(dst_path)
                    m.filename = dst_path.name
            else:
                shutil.copy2(src, dst_path)
            log.status = "done"
            done += 1
        except Exception as e:  # noqa: BLE001
            log.status = "failed"
            log.message = str(e)[:500]
            failed += 1
        db.add(log)
    db.commit()
    return {"batch_id": batch_id, "done": done, "failed": failed, "skipped": skipped,
            "total": sum(1 for i in plan["items"] if not i.get("excluded"))}


def undo_batch(db: Session, batch_id: str) -> dict:
    """撤销一个整理批次：move 移回原位，copy 删除副本（送回收站），重复文件夹移回。"""
    logs = (db.query(OrganizeLog)
            .filter(OrganizeLog.batch_id == batch_id, OrganizeLog.undone == 0,
                    OrganizeLog.status == "done").all())
    if not logs:
        raise ValueError("批次不存在、已撤销过或没有可撤销的动作")
    undo_batch_id = f"undo-{batch_id}"
    moved = copied_removed = failed = 0
    from send2trash import send2trash
    for log in logs:
        try:
            src = Path(log.dst_path)
            if not src.exists():
                log.undone = 1
                log.message = (log.message + " 撤销时目标已不存在").strip()
                continue
            if log.action == "move":
                dst = Path(log.src_path)
                dst.parent.mkdir(parents=True, exist_ok=True)
                if dst.exists():
                    dst = dst.with_name(f"{dst.stem}_restored{dst.suffix}")
                shutil.move(str(src), dst)
                m = db.get(MediaFile, log.media_file_id) if log.media_file_id else None
                if m and m.path == str(src):
                    m.path = str(dst)
                    m.filename = dst.name
                    m.status = "active"
                moved += 1
            elif log.action == "copy":
                send2trash(str(src))
                copied_removed += 1
            elif log.action in {"move_duplicate", "trash", "delete"}:
                if log.action == "delete":
                    log.undone = 1
                    log.message = (log.message + " 永久删除无法撤销").strip()
                    continue
                # 重复文件曾移入「重复文件」文件夹或回收站：仅 move_duplicate 可回移
                if log.action == "move_duplicate":
                    dst = Path(log.src_path)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    if dst.exists():
                        dst = dst.with_name(f"{dst.stem}_restored{dst.suffix}")
                    shutil.move(str(src), dst)
                    m = db.get(MediaFile, log.media_file_id) if log.media_file_id else None
                    if m:
                        m.path = str(dst)
                        m.filename = dst.name
                        m.status = "active"
                    moved += 1
            else:
                continue
            log.undone = 1
            db.add(OrganizeLog(batch_id=undo_batch_id, media_file_id=log.media_file_id,
                               src_path=log.dst_path, dst_path=log.src_path,
                               action=f"undo_{log.action}", status="done",
                               message=f"撤销批次 {batch_id}"))
        except Exception as e:  # noqa: BLE001
            failed += 1
            db.add(OrganizeLog(batch_id=undo_batch_id, media_file_id=log.media_file_id,
                               src_path=log.dst_path, dst_path=log.src_path,
                               action=f"undo_{log.action}", status="failed",
                               message=str(e)[:500]))
    db.commit()
    return {"batch_id": undo_batch_id, "moved_back": moved, "copies_removed": copied_removed,
            "failed": failed, "total": len(logs)}


def get_logs(db: Session, limit: int = 50) -> list[dict]:
    """按批次汇总整理历史。"""
    logs = db.query(OrganizeLog).order_by(OrganizeLog.id.desc()).limit(limit * 3).all()
    batches: dict[str, dict] = {}
    for log in reversed(logs):
        b = batches.setdefault(log.batch_id, {
            "batch_id": log.batch_id, "created_at": log.created_at.isoformat(),
            "total": 0, "done": 0, "failed": 0, "skipped": 0, "action": log.action,
            "undone": True,
        })
        b["total"] += 1
        if log.status == "done":
            b["done"] += 1
        elif log.status == "failed":
            b["failed"] += 1
        else:
            b["skipped"] += 1
        if log.undone == 0 and log.status == "done" and log.action in {"move", "copy", "move_duplicate"}:
            b["undone"] = False
    return list(batches.values())[-limit:]


def export_batch_csv(db: Session, batch_id: str) -> str:
    """导出批次日志为 CSV 文本（utf-8-sig，Excel 友好）。"""
    logs = (db.query(OrganizeLog).filter(OrganizeLog.batch_id == batch_id)
            .order_by(OrganizeLog.id.asc()).all())
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["时间", "动作", "结果", "源路径", "目标路径", "备注"])
    action_labels = {"move": "移动", "copy": "复制", "skip": "跳过", "delete": "删除",
                     "trash": "移入回收站", "move_duplicate": "移入重复文件夹"}
    status_labels = {"done": "成功", "failed": "失败", "skipped": "跳过"}
    for log in logs:
        writer.writerow([
            log.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            action_labels.get(log.action, log.action),
            status_labels.get(log.status, log.status),
            log.src_path, log.dst_path, log.message,
        ])
    return buf.getvalue()


def _md5_of(path: str) -> str | None:
    import hashlib
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()
