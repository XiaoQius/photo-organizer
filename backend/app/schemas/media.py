from datetime import datetime

from pydantic import BaseModel


class MediaOut(BaseModel):
    id: int
    path: str
    filename: str
    ext: str
    media_type: str
    size: int
    mtime: float
    taken_at: datetime | None = None
    taken_source: str | None = None
    width: int | None = None
    height: int | None = None
    md5: str | None = None
    phash: str | None = None
    status: str
    category: str = "normal"
    city: str | None = None
    gps_lat: float | None = None
    gps_lon: float | None = None
    blur_score: float | None = None
    quality_flag: str | None = None
    tags: list[str] | None = None
    codec: str | None = None

    model_config = {"from_attributes": True}


class MediaListOut(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[MediaOut]


class ScanStartIn(BaseModel):
    source_dir: str


class FsListOut(BaseModel):
    path: str
    parent: str | None = None
    directories: list[str]


class OrganizePlanIn(BaseModel):
    target_dir: str
    mode: str = "move"                # move / copy
    folder_structure: str = "Y/M"     # 预设，见 FOLDER_PRESETS
    naming: str = "standard"          # 预设，见 NAME_PRESETS
    folder_template: str = ""         # 自定义目录模板，优先于预设
    name_template: str = ""           # 自定义文件名模板，优先于预设
    media_ids: list[int] | None = None  # 空 = 全部


class OrganizePlanItem(BaseModel):
    media_id: int
    filename: str
    media_type: str
    src: str
    dst: str
    dst_dir: str
    action: str
    note: str = ""
    size: int
    excluded: bool = False


class OrganizePlanOut(BaseModel):
    plan_id: str
    items: list[OrganizePlanItem]


class OrganizePlanUpdateIn(BaseModel):
    excluded_ids: list[int] | None = None
    dst_overrides: dict[int, str] | None = None


class OrganizeExecuteIn(BaseModel):
    plan_id: str


class OrganizeUndoIn(BaseModel):
    batch_id: str


class CleanupIn(BaseModel):
    ids: list[int]
    action: str = "trash"             # trash / move
    target_dir: str = ""
    confirm_trash: bool = False       # trash 需确认


class ConvertIn(BaseModel):
    media_ids: list[int]
    quality: int = 90


class DuplicatesResolveIn(BaseModel):
    keep_ids: list[int]
    remove_ids: list[int]
    action: str = "move"              # move / trash
    duplicates_dir: str = ""
    confirm_trash: bool = False       # action=trash 时必须为 True
