"""统计总览：类型、年度分布、类别、质检与重复情况。"""

from sqlalchemy.orm import Session

from app.models.media import MediaFile


def overview(db: Session) -> dict:
    files = db.query(MediaFile).filter(MediaFile.status == "active").all()
    by_type: dict[str, int] = {}
    size_by_type: dict[str, int] = {}
    by_year: dict[str, int] = {}
    no_date = 0
    screenshot = chat_export = flagged = tagged = located = 0
    for m in files:
        by_type[m.media_type] = by_type.get(m.media_type, 0) + 1
        size_by_type[m.media_type] = size_by_type.get(m.media_type, 0) + m.size
        if m.taken_at:
            year = str(m.taken_at.year)
        else:
            year = "未知"
            no_date += 1
        by_year[year] = by_year.get(year, 0) + 1
        if m.category == "screenshot":
            screenshot += 1
        elif m.category == "chat_export":
            chat_export += 1
        if m.quality_flag:
            flagged += 1
        if m.tags:
            tagged += 1
        if m.city:
            located += 1

    # 完全重复文件数（组内除第一个外的数量）
    by_md5: dict[str, int] = {}
    for m in files:
        if m.md5:
            by_md5[m.md5] = by_md5.get(m.md5, 0) + 1
    duplicate_count = sum(c - 1 for c in by_md5.values() if c > 1)

    return {
        "total_count": len(files),
        "total_size": sum(size_by_type.values()),
        "photo_count": by_type.get("photo", 0),
        "photo_size": size_by_type.get("photo", 0),
        "video_count": by_type.get("video", 0),
        "video_size": size_by_type.get("video", 0),
        "doc_count": by_type.get("doc", 0),
        "doc_size": size_by_type.get("doc", 0),
        "audio_count": by_type.get("audio", 0),
        "audio_size": size_by_type.get("audio", 0),
        "archive_count": by_type.get("archive", 0),
        "archive_size": size_by_type.get("archive", 0),
        "duplicate_count": duplicate_count,
        "no_date_count": no_date,
        "screenshot_count": screenshot,
        "chat_export_count": chat_export,
        "flagged_count": flagged,
        "tagged_count": tagged,
        "located_count": located,
        "by_year": dict(sorted(by_year.items(), reverse=True)),
    }
