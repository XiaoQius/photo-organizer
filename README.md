# 照片视频整理工具（Photo Organizer）

本地运行的照片视频整理工具：扫描目录 → 按拍摄时间/地点/类别自动归档 → 统一重命名 → 重复与废片清理。所有整理操作先生成预览计划，确认后才执行，支持一键撤销。

## 功能特性

| 功能 | 说明 |
|------|------|
| 📁 目录扫描 | 后台线程扫描，实时进度，增量扫描跳过未变化文件；可选包含文档/音频/压缩包 |
| 🕐 智能时间识别 | EXIF → 视频容器创建时间（MP4/MOV）→ 文件名日期 → 修改时间，四层回退 |
| ⏱️ 拍摄时间修复 | 照片墙多选后批量校准时间：整体平移（相机时钟快/慢）或设为指定时间（扫描件/无 EXIF），JPEG 无损写回 EXIF 画质不变 |
| 📦 全类型整理 | 除照片视频外，还可扫描整理文档（pdf/office/文本）、音频、压缩包，统一按 {类型}/{时间} 归档，重命名前缀 DOC/AUD/ARC |
| 📍 地点识别 | 读取 EXIF GPS，内置 150+ 城市坐标离线反解城市名，可按城市归档 |
| 🏷️ 类别识别 | 自动识别截图（Screenshot_/截屏…）和聊天导出（微信图片_/mmexport/WA…），支持单独清理 |
| 🩺 废片检测 | 拉普拉斯方差检测模糊、亮度均值检测过暗/过曝，可批量送回收站或移入待清理 |
| 📂 模板化归档 | 目录模板 `{year}/{month}/{day}/{city}/{category}/{type}`、命名模板 `{prefix}/{datetime}/{original}`，任意组合 |
| 🔍 重复检测 | MD5 精确重复（全类型）；图片 BK-tree 感知哈希相似检测（可扩展到几十万张）；视频三帧指纹相似检测（需 ffmpeg） |
| ✅ 自由勾选清理 | 照片墙与清理中心所有列表均可自由点选任意文件批量送回收站或移动，重复检测支持「智能预选」一键勾掉每组多余文件 |
| ↩️ 一键撤销 | 每个整理批次可撤销：移动的文件移回原位，复制的副本送回收站 |
| 🧹 空文件夹清理 | 移动整理完成后可一键自底向上清理源目录中的空文件夹 |
| 🗑️ 回收站删除 | 清理动作默认送系统回收站（send2trash），可还原不丢数据 |
| ✏️ 计划可编辑 | 预览表格中可逐个排除文件、手动修改任意文件的目标路径 |
| 🖼️ 照片墙 | 无限滚动缩略图，按类型/类别/废片/年/月/标签/源目录筛选（选父目录自动包含子目录），排序切换（最新/最旧/最大/文件名），时间轴分组浏览（按年月分段），「那年今天」回忆视图，可开启「显示源目录」；缩略图自动应用 EXIF 方向（手机竖拍不躺倒）；大图预览支持键盘 ←→ 翻阅，视频在线播放；多选批量清理 |
| 💾 数据库备份 | 设置页一键备份/恢复 SQLite 数据库（在线备份，恢复前自动再存一份当前库），备份列表可管理 |
| 🤖 AI 打标 | 接 OpenAI 兼容视觉接口，自动为照片生成中文场景标签（可选） |
| 👀 文件夹监控 | 每分钟检查监控目录，自动入库，可选自动按规则归档新文件，支持「立即检查一次」 |
| 📄 报告导出 | 整理批次导出 CSV（Excel 友好，含 BOM） |
| 🔄 HEIC 转换 | 一键将 HEIC/HEIF 批量转为 JPG（需 pillow-heif） |

## 技术栈

- **前端**: React 18 + TypeScript + Vite + Ant Design 5
- **后端**: Python 3.12 + FastAPI + SQLAlchemy 2.0
- **图像处理**: Pillow（EXIF/GPS、缩略图、dHash、拉普拉斯质检）
- **回收站**: Send2Trash
- **视频封面/指纹**: ffmpeg（可选，未安装时优雅降级）
- **AI**: OpenAI 兼容接口（可选，环境变量配置）
- **数据库**: SQLite（零配置，含轻量列迁移）

## 快速开始

```bash
cd photo-organizer/backend
pip install -r requirements.txt
python -m app.main
```

浏览器访问 **http://localhost:8010**（后端同时托管前端产物，单服务启动）。

可选增强：
- HEIC 支持/转换：`pip install pillow-heif`
- 视频封面与视频相似检测：安装 [ffmpeg](https://ffmpeg.org) 并加入 PATH
- AI 打标：设置环境变量 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` 后重启

### 打包成独立程序（免 Python 环境）

```bash
cd frontend && npm run build          # 先构建前端
cd ../backend
pip install pyinstaller
pyinstaller --noconfirm --clean --name PhotoOrganizer --workpath build --distpath ../dist ^
  --add-data "../frontend/dist;frontend_dist" --add-data "app/data/cities.json;app/data" ^
  --collect-all uvicorn --hidden-import piexif run.py
```

产物在 `dist/PhotoOrganizer/`：双击 `PhotoOrganizer.exe` 自动打开浏览器（端口被占用时自动后移），
数据保存在程序旁的 `data/` 文件夹，整体拷贝即可备份。

### 开发模式（前后端分离）

```bash
# 终端 1：后端（端口 8010）
cd photo-organizer/backend && python -m app.main

# 终端 2：前端（端口 5174，代理 API 到 8010）
cd photo-organizer/frontend && npm install && npm run dev
```

## 使用流程

1. **扫描** → 仪表盘选择目录开始扫描 → 查看统计（类型/年度/类别/废片/重复/地点）
2. **质检** → 仪表盘「运行废片质检」补算清晰度标记
3. **浏览** → 照片墙按类别/废片/年月/标签筛选；配置 LLM 后可一键 AI 打标
4. **整理** → 整理归档页选目标目录与规则（预设或模板）→ 生成预览 → 可排除/改路径 → 确认执行
5. **后悔** → 整理历史中一键「撤销」，或导出 CSV 留档
6. **清理** → 清理中心处理重复文件、疑似废片、截图与聊天导出（默认进回收站或重复文件夹）
7. **自动化** → 设置页开启文件夹监控，新照片自动入库/归档

## 归档模板说明

| 模板变量 | 含义 | 示例值 |
|----------|------|--------|
| `{year}` `{month}` `{day}` | 拍摄日期 | 2024 / 05 / 01 |
| `{city}` | GPS 反解城市，无定位为「未知地点」 | 桂林 |
| `{category}` | 类别 | 照片 / 截图 / 聊天导出 |
| `{type}` | 媒体类型 | 照片 / 视频 |
| `{prefix}` | 文件名前缀 | IMG / VID |
| `{datetime}` | 拍摄时间戳 | 20240501_103000 |
| `{original}` | 原文件名（不含扩展名） | vacation_001 |

预设：`年/月`、`年/月/日`、`年/月/城市`、`年/城市`、`类别/年/月`，或完全自定义如 `{year}/{month}/{city}/{category}`。

## 项目结构

```
photo-organizer/
├── backend/app/
│   ├── main.py            # FastAPI 入口（端口 8010）
│   ├── config.py          # 常量与默认设置
│   ├── database.py        # SQLAlchemy + 轻量列迁移
│   ├── models/            # MediaFile / OrganizeLog / Setting
│   ├── schemas/           # Pydantic 模型
│   ├── api/               # scan / media / organize / duplicates / stats / settings / ai / watch / jobs
│   ├── services/          # 扫描、时间提取、分类质检、定位、哈希、BK-tree、整理、撤销、AI、监控、转换
│   └── data/cities.json   # 内置城市坐标集（离线定位）
├── frontend/src/
│   ├── pages/             # Dashboard / Gallery / Organize / Duplicates(清理中心) / Settings
│   ├── components/        # Layout + FolderPicker
│   └── services/api.ts
└── make_test_media.py     # 生成测试媒体（EXIF/GPS/伪 MP4 等）
```

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/scan/start | 启动后台扫描 |
| GET | /api/media | 媒体列表（类型/类别/质量/标签/年月筛选） |
| POST | /api/media/analyze | 后台补算废片质检 |
| POST | /api/media/cleanup | 批量送回收站/移入待清理（需确认） |
| POST | /api/media/convert | HEIC 批量转 JPG |
| POST | /api/organize/plan | 生成整理计划（支持模板） |
| PATCH | /api/organize/plan/:id | 编辑计划（排除文件/改目标路径） |
| POST | /api/organize/execute | 执行计划 |
| POST | /api/organize/undo | 撤销整理批次 |
| GET | /api/organize/logs/export | 批次 CSV 导出 |
| GET | /api/duplicates | 重复/相似分组（图片 BK-tree + 视频指纹） |
| POST | /api/duplicates/resolve | 处理重复（移入重复文件夹/回收站） |
| POST | /api/ai/tag | AI 场景打标（后台任务） |
| GET/POST | /api/watch/* | 文件夹监控状态/开关 |
| GET | /api/jobs/:id | 通用后台任务进度 |
| GET | /api/stats/overview | 统计总览 |

## 安全说明

- 扫描只读；整理必须先预览、后确认
- 目标已有相同文件自动跳过，不同内容加序号，不覆盖
- 撤销可回移文件；删除类动作默认送系统回收站（send2trash）
- 回收站删除等危险操作需前端二次确认 + 后端 `confirm_trash` 显式校验
- 所有动作记录在 `organize_logs`，可导出 CSV 审计
