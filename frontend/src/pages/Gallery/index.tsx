import { Fragment, useCallback, useEffect, useRef, useState } from 'react'
import type { KeyboardEvent as ReactKeyboardEvent, MouseEvent as ReactMouseEvent } from 'react'
import {
  Alert,
  Button,
  Card,
  Checkbox,
  DatePicker,
  Empty,
  FloatButton,
  Image as AntImage,
  Input,
  InputNumber,
  Modal,
  Progress,
  Radio,
  Segmented,
  Select,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from 'antd'
import dayjs, { Dayjs } from 'dayjs'
import {
  CheckCircleFilled,
  ClockCircleOutlined,
  WarningOutlined,
  DeleteOutlined,
  FileTextOutlined,
  FileZipOutlined,
  PlayCircleOutlined,
  RobotOutlined,
  SoundOutlined,
  SwapOutlined,
  VideoCameraOutlined,
} from '@ant-design/icons'
import PageHeader from '../../components/PageHeader'
import { useSearchParams } from 'react-router-dom'
import { EyeOutlined } from '@ant-design/icons'
import { aiApi, jobsApi, mediaApi } from '../../services/api'
import type { BackgroundJob, MediaFile, MediaFilter } from '../../types'

const PAGE_SIZE = 60

const QUALITY_LABELS: Record<string, string> = {
  blurry: '模糊',
  dark: '过暗',
  bright: '过曝',
}

function formatSize(bytes: number) {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} GB`
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${(bytes / 1024).toFixed(0)} KB`
}

export default function Gallery() {
  const [items, setItems] = useState<MediaFile[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [searchParams, setSearchParams] = useSearchParams()
  const [mediaType, setMediaType] = useState<string>(searchParams.get('type') ?? 'all')
  const [category, setCategory] = useState<string>(searchParams.get('category') ?? 'all')
  const [quality, setQuality] = useState<string>(searchParams.get('quality') ?? 'all')
  const [tag, setTag] = useState('')
  const [year, setYear] = useState<number | undefined>()
  const [month, setMonth] = useState<number | undefined>()
  const [years, setYears] = useState<number[]>([])
  const [dirs, setDirs] = useState<{ dir: string; count: number }[]>([])
  const [dirFilter, setDirFilter] = useState<string | undefined>()
  const [showDir, setShowDir] = useState(false)
  const [onThisDay, setOnThisDay] = useState(false)
  const [order, setOrder] = useState<MediaFilter['order']>('time_desc')
  const [loading, setLoading] = useState(false)
  const [hasMore, setHasMore] = useState(true)
  const [playing, setPlaying] = useState<MediaFile | null>(null)
  // 批量清理选择模式
  const [selecting, setSelecting] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [moveDir, setMoveDir] = useState('')
  const [cleaning, setCleaning] = useState(false)
  const [selectingAll, setSelectingAll] = useState(false)
  const [cleanJob, setCleanJob] = useState<{ job_id: string; total: number } | null>(null)
  const [fixJob, setFixJob] = useState<{ job_id: string; total: number } | null>(null)
  const lastClickedRef = useRef<number | null>(null)
  const AUTO_LOAD_CAP = 600
  // 修复拍摄时间
  const [fixOpen, setFixOpen] = useState(false)
  const [fixMode, setFixMode] = useState<'shift' | 'set'>('shift')
  const [fixDays, setFixDays] = useState(0)
  const [fixHours, setFixHours] = useState(0)
  const [fixSetTime, setFixSetTime] = useState<Dayjs | null>(null)
  const [fixWorking, setFixWorking] = useState(false)
  // 时间轴分组
  const [timeline, setTimeline] = useState(false)
  const [previewing, setPreviewing] = useState<MediaFile | null>(null)
  const [videoError, setVideoError] = useState(false)
  const [thumbFailed, setThumbFailed] = useState<Set<number>>(new Set())
  // AI 打标
  const [aiConfigured, setAiConfigured] = useState(false)
  const [aiJob, setAiJob] = useState<BackgroundJob | null>(null)
  const aiTimer = useRef<number | null>(null)
  const sentinelRef = useRef<HTMLDivElement | null>(null)

  const [ffmpegReady, setFfmpegReady] = useState<boolean | null>(null)

  useEffect(() => {
    mediaApi.years().then((r) => setYears(r.years)).catch(() => {})
    aiApi.config().then((c) => setAiConfigured(c.configured)).catch(() => {})
    mediaApi.env().then((e) => setFfmpegReady(e.ffmpeg)).catch(() => setFfmpegReady(null))
  }, [])

  const load = useCallback((nextPage: number, append: boolean) => {
    setLoading(true)
    mediaApi
      .list({
        page: nextPage,
        page_size: PAGE_SIZE,
        media_type: mediaType === 'all' ? '' : mediaType,
        category: category === 'all' ? '' : category,
        quality: quality === 'all' ? '' : quality,
        tag: tag.trim(),
        year,
        month,
        dir: dirFilter,
        on_this_day: onThisDay ? 1 : 0,
        order,
      })
      .then((r) => {
        setItems((prev) => (append ? [...prev, ...r.items] : r.items))
        setTotal(r.total)
        setHasMore(nextPage * PAGE_SIZE < r.total)
        setPage(nextPage)
      })
      .catch((e) => message.error(e.response?.data?.detail || '加载失败'))
      .finally(() => setLoading(false))
    // 首页加载时同步刷新源目录列表（清理/扫描后可能变化）
    if (nextPage === 1) {
      mediaApi.dirs().then((r) => setDirs(r.dirs)).catch(() => {})
    }
  }, [mediaType, category, quality, tag, year, month, dirFilter, onThisDay, order])

  // 筛选变化时重新加载，并同步到网址（刷新/返回不丢失）
  useEffect(() => {
    load(1, false)
  }, [load])

  useEffect(() => {
    const sp = new URLSearchParams()
    if (mediaType !== 'all') sp.set('type', mediaType)
    if (category !== 'all') sp.set('category', category)
    if (quality !== 'all') sp.set('quality', quality)
    setSearchParams(sp, { replace: true })
  }, [mediaType, category, quality, setSearchParams])

  // 无限滚动
  useEffect(() => {
    const el = sentinelRef.current
    if (!el) return
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMore && !loading && items.length < AUTO_LOAD_CAP) {
          load(page + 1, true)
        }
      },
      { rootMargin: '400px' },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [hasMore, loading, page, load])

  // 快捷键：选择模式下 Esc 退出，Ctrl+A 全选已加载
  useEffect(() => {
    if (!selecting) return
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key === 'Escape') exitSelecting()
      else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') {
        e.preventDefault()
        setSelectedIds(new Set(items.map((m) => m.id)))
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [selecting, items])

  // AI 打标进度轮询
  useEffect(() => {
    if (aiJob?.status === 'running') {
      aiTimer.current = window.setInterval(() => {
        aiApi.status(aiJob.job_id).then((res) => {
          setAiJob(res)
          if (res.status !== 'running') load(1, false)
        }).catch(() => {})
      }, 1500)
    }
    return () => {
      if (aiTimer.current) window.clearInterval(aiTimer.current)
    }
  }, [aiJob?.job_id, aiJob?.status, load])

  // 大批量清理/时间修复的后台进度轮询
  useEffect(() => {
    if (!cleanJob) return
    const timer = window.setInterval(async () => {
      try {
        const res = await jobsApi.status(cleanJob.job_id)
        if (res.status === 'done' || res.status === 'error') {
          window.clearInterval(timer)
          setCleanJob(null)
          if (res.status === 'error') {
            message.error(`清理失败：${res.error}`)
          } else {
            const r = res.result as { done?: number; failed?: number }
            message.success(`清理完成：成功 ${r.done ?? 0} 个${r.failed ? `，失败 ${r.failed} 个` : ''}`)
          }
          exitSelecting()
          load(1, false)
        }
      } catch { /* 忽略单次轮询失败 */ }
    }, 800)
    return () => window.clearInterval(timer)
  }, [cleanJob])

  useEffect(() => {
    if (!fixJob) return
    const timer = window.setInterval(async () => {
      try {
        const res = await jobsApi.status(fixJob.job_id)
        if (res.status === 'done' || res.status === 'error') {
          window.clearInterval(timer)
          setFixJob(null)
          if (res.status === 'error') {
            message.error(`修复失败：${res.error}`)
          } else {
            const r = res.result as { updated?: number }
            message.success(`已更新 ${r.updated ?? 0} 个文件的拍摄时间`)
          }
          setFixOpen(false)
          load(1, false)
        }
      } catch { /* 忽略单次轮询失败 */ }
    }, 800)
    return () => window.clearInterval(timer)
  }, [fixJob])

  const startTagging = () => {
    aiApi
      .startTagging(200)
      .then(({ job_id }) => {
        message.info('AI 打标已开始')
        setAiJob({ job_id, status: 'running', total: 0, processed: 0, current: '', result: {}, error: '', kind: 'ai_tag', label: '' })
      })
      .catch((e) => message.error(e.response?.data?.detail || '启动失败'))
  }

  const aiPercent = aiJob && aiJob.total > 0 ? Math.round((aiJob.processed / aiJob.total) * 100) : 0

  // —— 时间轴分组：按拍摄年月分段（保持当前排序顺序） ——
  const renderList = (() => {
    if (!timeline) return [{ key: 'all', label: '', files: items }]
    const map = new Map<string, MediaFile[]>()
    for (const m of items) {
      const d = m.taken_at ? dayjs(m.taken_at) : dayjs(m.mtime * 1000)
      const label = d.format('YYYY年MM月')
      const arr = map.get(label)
      if (arr) arr.push(m)
      else map.set(label, [m])
    }
    return [...map.entries()].map(([label, files]) => ({ key: label, label, files }))
  })()

  // —— 批量清理 ——
  // Shift+点击：从上次点击处区间连选（已加载范围内）
  const handleSelectClick = (id: number, e: ReactMouseEvent) => {
    if (e.shiftKey && lastClickedRef.current != null) {
      const ids = items.map((m) => m.id)
      const a = ids.indexOf(lastClickedRef.current)
      const b = ids.indexOf(id)
      if (a >= 0 && b >= 0) {
        const [s, t] = a < b ? [a, b] : [b, a]
        setSelectedIds((prev) => {
          const next = new Set(prev)
          for (let i = s; i <= t; i++) next.add(ids[i])
          return next
        })
        lastClickedRef.current = id
        return
      }
    }
    toggleSelect(id)
    lastClickedRef.current = id
  }

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const exitSelecting = () => {
    setSelecting(false)
    setSelectedIds(new Set())
  }

  // 选择当前筛选条件下的全部文件（含未滚动加载的），自动分页拉取
  const selectAllFiltered = async () => {
    setSelectingAll(true)
    try {
      const all = new Set<number>()
      const base = {
        media_type: mediaType === 'all' ? '' : mediaType,
        category: category === 'all' ? '' : category,
        quality: quality === 'all' ? '' : quality,
        tag: tag.trim(),
        year,
        month,
        dir: dirFilter,
        on_this_day: onThisDay ? 1 : 0,
      }
      for (let page = 1; ; page++) {
        const r = await mediaApi.list({ ...base, page, page_size: 500 })
        r.items.forEach((m) => all.add(m.id))
        if (page * 500 >= r.total) break
      }
      setSelectedIds(all)
      message.success(`已选择全部 ${all.size} 个文件（包含未加载的）`)
    } catch (e: any) {
      message.error(e.response?.data?.detail || '获取文件列表失败')
    } finally {
      setSelectingAll(false)
    }
  }

  const selectedItems = items.filter((m) => selectedIds.has(m.id))
  const selectedSize = selectedItems.reduce((s, m) => s + m.size, 0)

  const doCleanup = async (action: 'trash' | 'move') => {
    setCleaning(true)
    try {
      const r = await mediaApi.cleanup({
        ids: [...selectedIds],
        action,
        target_dir: moveDir.trim(),
        confirm_trash: action === 'trash',
      })
      if (r.job_id) {
        message.info(`文件较多，已转后台处理（共 ${selectedIds.size} 个）`)
        setCleanJob({ job_id: r.job_id, total: selectedIds.size })
        exitSelecting()
        return
      }
      message.success(`处理完成：成功 ${r.done} 个${r.failed ? `，失败 ${r.failed} 个` : ''}`)
      exitSelecting()
      load(1, false)
    } catch (e: any) {
      message.error(e.response?.data?.detail || '处理失败')
    } finally {
      setCleaning(false)
    }
  }

  const runCleanup = (action: 'trash' | 'move') => {
    if (selectedIds.size === 0) {
      message.warning('请先点选要清理的文件')
      return
    }
    if (action === 'trash') {
      Modal.confirm({
        title: '确认送入回收站？',
        content: `选中的 ${selectedIds.size} 个文件将移入系统回收站，可在回收站还原。`,
        okText: '送入回收站',
        okButtonProps: { danger: true },
        onOk: () => doCleanup('trash'),
      })
    } else {
      doCleanup('move')
    }
  }

  // —— 修复拍摄时间 ——
  const fixDeltaHours = fixDays * 24 + fixHours
  const firstSelected = items.find((m) => selectedIds.has(m.id))

  const submitFixTime = async () => {
    if (selectedIds.size === 0) return
    if (fixMode === 'shift' && fixDeltaHours === 0) {
      message.warning('平移量不能为 0')
      return
    }
    if (fixMode === 'set' && !fixSetTime) {
      message.warning('请选择目标时间')
      return
    }
    setFixWorking(true)
    try {
      const r = await mediaApi.fixTime({
        ids: [...selectedIds],
        mode: fixMode,
        delta_hours: fixDeltaHours,
        set_datetime: fixMode === 'set' ? fixSetTime!.format('YYYY-MM-DD HH:mm:ss') : undefined,
      })
      if (r.job_id) {
        message.info(`文件较多，已转后台处理`)
        setFixJob({ job_id: r.job_id, total: selectedIds.size })
        return
      }
      const note = r.exif_written ? `（${r.exif_written} 个 JPEG 已写回 EXIF）` : ''
      message.success(`已更新 ${r.updated} 个文件的拍摄时间${note}${r.skipped ? `，${r.skipped} 个仅更新数据库` : ''}`)
      setFixOpen(false)
      load(1, false)
    } catch (e: any) {
      message.error(e.response?.data?.detail || '修复失败')
    } finally {
      setFixWorking(false)
    }
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <PageHeader title="照片墙" subtitle="浏览、筛选、挑选需要处理的照片视频" />
      <Space wrap>
        <Segmented
          value={mediaType}
          onChange={(v) => setMediaType(v as string)}
          options={[
            { label: '全部', value: 'all' },
            { label: '照片', value: 'photo' },
            { label: '视频', value: 'video' },
            { label: '文档', value: 'doc' },
            { label: '音频', value: 'audio' },
            { label: '压缩包', value: 'archive' },
          ]}
        />
        <Segmented
          value={category}
          onChange={(v) => setCategory(v as string)}
          options={[
            { label: '全部类别', value: 'all' },
            { label: '拍照', value: 'normal' },
            { label: '截图', value: 'screenshot' },
            { label: '聊天导出', value: 'chat_export' },
          ]}
        />
        <Segmented
          value={quality}
          onChange={(v) => setQuality(v as string)}
          options={[
            { label: '全部质量', value: 'all' },
            { label: '疑似废片', value: 'flagged' },
            { label: '模糊', value: 'blurry' },
          ]}
        />
        <Select
          placeholder="年份"
          allowClear
          style={{ width: 110 }}
          value={year}
          options={years.map((y) => ({ label: `${y} 年`, value: y }))}
          onChange={(v) => { setYear(v); setMonth(undefined) }}
        />
        <Select
          placeholder="月份"
          allowClear
          disabled={!year}
          style={{ width: 110 }}
          value={month}
          options={Array.from({ length: 12 }, (_, i) => ({ label: `${i + 1} 月`, value: i + 1 }))}
          onChange={(v) => setMonth(v)}
        />
        <Input.Search
          placeholder="按标签筛选，如 风景"
          allowClear
          style={{ width: 180 }}
          value={tag}
          onChange={(e) => setTag(e.target.value)}
          onSearch={() => load(1, false)}
        />
        <Select
          placeholder="按源目录筛选"
          allowClear
          showSearch
          optionFilterProp="label"
          style={{ width: 280 }}
          value={dirFilter}
          options={dirs.map((d) => ({ label: `${d.dir}（${d.count}）`, value: d.dir }))}
          onChange={(v) => setDirFilter(v)}
        />
        <Checkbox
          checked={showDir}
          onChange={(e) => setShowDir(e.target.checked)}
        >
          显示源目录
        </Checkbox>
        <Button
          type={onThisDay ? 'primary' : 'default'}
          onClick={() => setOnThisDay((v) => !v)}
        >
          📅 那年今天
        </Button>
        <Checkbox checked={timeline} onChange={(e) => setTimeline(e.target.checked)}>
          时间轴分组
        </Checkbox>
        <Select
          placeholder="排序"
          style={{ width: 130 }}
          value={order}
          options={[
            { label: '最新优先', value: 'time_desc' },
            { label: '最旧优先', value: 'time_asc' },
            { label: '体积最大', value: 'size_desc' },
            { label: '按文件名', value: 'name' },
          ]}
          onChange={(v) => setOrder(v)}
        />
        <Typography.Text type="secondary">共 {total} 个文件</Typography.Text>
        {selecting ? (
          <Button onClick={exitSelecting}>退出选择</Button>
        ) : (
          <Button
            icon={<DeleteOutlined />}
            onClick={() => { setSelecting(true); setSelectedIds(new Set()) }}
          >
            批量清理
          </Button>
        )}
        {aiConfigured && (
          <Button icon={<RobotOutlined />} loading={aiJob?.status === 'running'} onClick={startTagging}>
            AI 打标（最近 200 张）
          </Button>
        )}
      </Space>

      {ffmpegReady === false && (
        <Alert
          type="info"
          showIcon
          message="未检测到 ffmpeg：视频封面和视频相似检测不可用"
          action={
            <Button size="small" href="https://www.gyan.dev/ffmpeg/builds/" target="_blank">
              下载 ffmpeg
            </Button>
          }
        />
      )}

      {aiJob && aiJob.status === 'running' && (
        <Card>
          <Progress percent={aiPercent} status="active" />
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            {aiJob.current || '正在识别…'}（{aiJob.processed}/{aiJob.total || '?'}）
          </Typography.Text>
        </Card>
      )}
      {aiJob && (aiJob.status === 'done' || aiJob.status === 'error') && (
        <Typography.Text type={aiJob.status === 'error' ? 'danger' : 'secondary'} style={{ fontSize: 12 }}>
          {aiJob.status === 'error'
            ? `AI 打标失败：${aiJob.error}`
            : `AI 打标完成，共标记 ${aiJob.result?.tagged ?? 0} 张`}
        </Typography.Text>
      )}

      {selecting && cleanJob && (
        <Card size="small" className="glass-bar" styles={{ body: { padding: "10px 14px" } }}>
          <Progress status="active" size="small" />
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            正在后台清理 {cleanJob.total} 个文件，完成后会自动刷新，可继续浏览其他页面
          </Typography.Text>
        </Card>
        )}
        {selecting && !cleanJob && (
        <Card size="small" className="glass-bar" styles={{ body: { padding: "10px 14px" } }}>
          <Space wrap>
            <Typography.Text strong>
              已选 {selectedIds.size} 个（{formatSize(selectedSize)}）
            </Typography.Text>
            <Button size="small" onClick={() => setSelectedIds(new Set(items.map((m) => m.id)))}>
              全选已加载
            </Button>
            <Button size="small" type="primary" ghost loading={selectingAll}
                    disabled={total === 0} onClick={selectAllFiltered}>
              选择全部结果（{total}）
            </Button>
            <Button size="small" onClick={() => setSelectedIds(new Set())} disabled={selectedIds.size === 0}>
              清空选择
            </Button>
            <Button size="small" icon={<ClockCircleOutlined />} disabled={selectedIds.size === 0}
                    onClick={() => setFixOpen(true)}>
              修复拍摄时间
            </Button>
            <Button danger icon={<DeleteOutlined />} disabled={selectedIds.size === 0}
                    loading={cleaning} onClick={() => runCleanup('trash')}>
              送入回收站
            </Button>
            <Input
              placeholder="移动到指定文件夹（留空则移到原目录下「待清理」）"
              style={{ width: 300 }}
              value={moveDir}
              onChange={(e) => setMoveDir(e.target.value)}
            />
            <Button icon={<SwapOutlined />} disabled={selectedIds.size === 0}
                    loading={cleaning} onClick={() => runCleanup('move')}>
              移动
            </Button>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              点击选择、Shift+点击连选一段；Esc 退出、Ctrl+A 全选已加载；删除先进回收站
            </Typography.Text>
          </Space>
        </Card>
      )}

      <Spin spinning={loading && items.length === 0}>
        {items.length === 0 && !loading ? (
          <Empty description="没有找到媒体文件，请先在仪表盘扫描目录" style={{ marginTop: 80 }} />
        ) : (
          <AntImage.PreviewGroup>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
              gap: 12,
            }}
          >
            {renderList.map((sec) => (
              <Fragment key={sec.key}>
                {sec.label && (
                  <div style={{ gridColumn: '1 / -1', display: 'flex', alignItems: 'baseline', gap: 8, marginTop: 8 }}>
                    <Typography.Title level={5} style={{ margin: 0 }}>{sec.label}</Typography.Title>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>{sec.files.length} 个文件</Typography.Text>
                  </div>
                )}
                {sec.files.map((m) => (
              <div
                key={m.id}
                onClick={selecting ? (e) => handleSelectClick(m.id, e) : undefined}
                className="photo-tile"
                style={{
                  position: 'relative',
                  borderRadius: 8,
                  overflow: 'hidden',
                  background: '#f5f5f5',
                  aspectRatio: '1',
                  cursor: selecting ? 'pointer' : 'default',
                  outline: selecting && selectedIds.has(m.id) ? '3px solid #52c41a' : 'none',
                  outlineOffset: '-3px',
                }}
              >
                {selecting ? (
                  <img
                    src={mediaApi.thumbnailUrl(m.id)}
                    alt={m.filename}
                    loading="lazy"
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    onError={(e) => { (e.target as HTMLImageElement).style.visibility = 'hidden' }}
                  />
                ) : m.media_type === 'photo' ? (
                  <AntImage
                    src={mediaApi.fileUrl(m.id)}
                    fallback={mediaApi.thumbnailUrl(m.id)}
                    width="100%"
                    height="100%"
                    style={{ objectFit: 'cover' }}
                    preview={{ src: mediaApi.fileUrl(m.id) }}
                  />
                ) : m.media_type === 'video' ? (
                  <>
                    {thumbFailed.has(m.id) ? (
                      <div
                        onClick={() => setPlaying(m)}
                        style={{
                          display: 'flex', flexDirection: 'column', alignItems: 'center',
                          justifyContent: 'center', height: '100%', gap: 6, cursor: 'pointer',
                          background: 'linear-gradient(135deg, #2a3140, #1c212b)',
                        }}
                      >
                        <PlayCircleOutlined style={{ fontSize: 34, color: 'rgba(255,255,255,0.85)' }} />
                        <Typography.Text style={{ fontSize: 12, color: 'rgba(255,255,255,0.75)' }}>
                          {m.ext.slice(1).toUpperCase()} 视频{m.codec === 'hevc' ? ' · HEVC' : ''}
                        </Typography.Text>
                      </div>
                    ) : (
                      <img
                        src={mediaApi.thumbnailUrl(m.id)}
                        alt={m.filename}
                        loading="lazy"
                        style={{ width: '100%', height: '100%', objectFit: 'cover', cursor: 'pointer' }}
                        onClick={() => setPlaying(m)}
                        onError={() => setThumbFailed((prev) => new Set(prev).add(m.id))}
                      />
                    )}
                    {!thumbFailed.has(m.id) && (
                      <PlayCircleOutlined
                        onClick={() => setPlaying(m)}
                        style={{
                          position: 'absolute', inset: 0, margin: 'auto',
                          fontSize: 40, color: 'rgba(255,255,255,0.85)',
                          pointerEvents: 'none',
                        }}
                      />
                    )}
                  </>
                ) : m.media_type === 'audio' ? (
                  <div
                    onClick={() => setPlaying(m)}
                    style={{
                      display: 'flex', flexDirection: 'column', alignItems: 'center',
                      justifyContent: 'center', height: '100%', gap: 6, cursor: 'pointer',
                    }}
                  >
                    <SoundOutlined style={{ fontSize: 38, color: '#1677ff' }} />
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>{m.ext.slice(1).toUpperCase()} 音频</Typography.Text>
                  </div>
                ) : (
                  <div
                    onClick={() => setPlaying(m)}
                    style={{
                      display: 'flex', flexDirection: 'column', alignItems: 'center',
                      justifyContent: 'center', height: '100%', gap: 6, cursor: 'pointer',
                    }}
                  >
                    {m.media_type === 'archive'
                      ? <FileZipOutlined style={{ fontSize: 38, color: '#faad14' }} />
                      : <FileTextOutlined style={{ fontSize: 38, color: '#52c41a' }} />}
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      {m.media_type === 'archive' ? '压缩包' : '文档'} · {m.ext.slice(1).toUpperCase()}
                    </Typography.Text>
                  </div>
                )}
                {selecting && selectedIds.has(m.id) && (
                  <CheckCircleFilled style={{ position: 'absolute', top: 6, left: 6, fontSize: 22, color: '#52c41a' }} />
                )}
                {selecting && m.media_type === 'photo' && (
                  <Button
                    size="small"
                    icon={<EyeOutlined />}
                    onClick={(e) => { e.stopPropagation(); setPreviewing(m) }}
                    style={{ position: 'absolute', top: 6, right: 6 }}
                  />
                )}
                <div
                  style={{
                    position: 'absolute', bottom: 0, left: 0, right: 0,
                    padding: '4px 8px', fontSize: 12, color: '#fff',
                    background: 'linear-gradient(transparent, rgba(0,0,0,0.65))',
                  }}
                >
                  <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {m.filename}
                  </div>
                  {showDir && (
                    <div style={{ fontSize: 11, opacity: 0.8, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      📁 {m.path.slice(0, m.path.length - m.filename.length - 1)}
                    </div>
                  )}
                </div>
                <Space size={2} style={{ position: 'absolute', top: 6, left: 6, flexWrap: 'wrap', display: selecting ? 'none' : undefined }}>
                  {m.category === 'screenshot' && <Tag color="orange" style={{ margin: 0 }}>截图</Tag>}
                  {m.category === 'chat_export' && <Tag color="purple" style={{ margin: 0 }}>聊天导出</Tag>}
                  {m.quality_flag && <Tag color="red" style={{ margin: 0 }}>{QUALITY_LABELS[m.quality_flag]}</Tag>}
                  {m.city && <Tag color="geekblue" style={{ margin: 0 }}>{m.city}</Tag>}
                  {m.tags && m.tags.slice(0, 2).map((t) => (
                    <Tag key={t} color="green" style={{ margin: 0 }}>{t}</Tag>
                  ))}
                </Space>
              </div>
            ))}
              </Fragment>
            ))}
          </div>
          </AntImage.PreviewGroup>
        )}
        <div ref={sentinelRef} style={{ height: 1 }} />
        {loading && items.length > 0 && (
          <div style={{ textAlign: 'center', padding: 16 }}><Spin /></div>
        )}
        {hasMore && items.length >= AUTO_LOAD_CAP && (
          <div style={{ textAlign: 'center', padding: 16 }}>
            <Button onClick={() => load(page + 1, true)} loading={loading}>
              加载更多（已加载 {items.length} / {total}）
            </Button>
            <Typography.Text type="secondary" style={{ display: 'block', fontSize: 12, marginTop: 8 }}>
              为保持流畅，超过 {AUTO_LOAD_CAP} 张后改为手动加载；可用筛选缩小范围
            </Typography.Text>
          </div>
        )}
        {!hasMore && items.length > 0 && (
          <Typography.Text type="secondary" style={{ display: 'block', textAlign: 'center', padding: 16 }}>
            已加载全部 {total} 个文件
          </Typography.Text>
        )}
      </Spin>

      <Modal
        open={!!playing}
        title={playing?.filename}
        footer={null}
        width={860}
        onCancel={() => { setPlaying(null); setVideoError(false) }}
        destroyOnClose
      >
        {playing && playing.media_type === 'video' && (
          <>
            {playing.codec === 'hevc' && (
              <Alert
                type="warning"
                showIcon
                message="此视频为 HEVC/H.265 编码，多数浏览器无法直接播放"
                description={
                  <Space direction="vertical" size={4}>
                    <span>点击下方按钮用系统播放器（PotPlayer / 暴风等）打开，画质原样。</span>
                    <Button size="small" type="primary" onClick={() => mediaApi.openInSystem(playing.id).then(() => message.success('已调用系统播放器')).catch((e) => message.error(e.response?.data?.detail || '打开失败'))}>
                      用系统播放器打开
                    </Button>
                  </Space>
                }
                style={{ marginBottom: 12 }}
              />
            )}
            <video
              key={playing.id}
              src={mediaApi.fileUrl(playing.id)}
              controls
              autoPlay
              onError={() => setVideoError(true)}
              style={{ width: '100%', maxHeight: '60vh', background: '#000', display: videoError ? 'none' : undefined }}
            />
            {videoError && !playing.codec && (
              <Alert
                type="info"
                showIcon
                message="浏览器无法播放此视频"
                description={<Button size="small" type="primary" onClick={() => mediaApi.openInSystem(playing.id).then(() => message.success('已调用系统播放器'))}>用系统播放器打开</Button>}
              />
            )}
          </>
        )}
        {playing && playing.media_type === 'audio' && (
          <div style={{ padding: '24px 8px', textAlign: 'center' }}>
            <SoundOutlined style={{ fontSize: 56, color: '#1677ff' }} />
            <audio key={playing.id} src={mediaApi.fileUrl(playing.id)} controls autoPlay style={{ width: '100%', marginTop: 16 }} />
          </div>
        )}
        {playing && (playing.media_type === 'doc' || playing.media_type === 'archive') && (
          <div style={{ padding: '24px 8px', textAlign: 'center' }}>
            {playing.media_type === 'archive'
              ? <FileZipOutlined style={{ fontSize: 56, color: '#faad14' }} />
              : <FileTextOutlined style={{ fontSize: 56, color: '#52c41a' }} />}
            <div style={{ marginTop: 16 }}>
              <Button type="primary" href={mediaApi.fileUrl(playing.id)} target="_blank">
                打开文件
              </Button>
            </div>
          </div>
        )}
        {playing && (
          <Space direction="vertical" size={2} style={{ marginTop: 12 }}>
            <Typography.Text>{playing.path}</Typography.Text>
            <Space wrap>
              <Tag icon={<VideoCameraOutlined />}>{formatSize(playing.size)}</Tag>
              <Tag color="blue">
                {playing.taken_at ? new Date(playing.taken_at).toLocaleString('zh-CN') : '未知时间'}
              </Tag>
              {playing.city && <Tag color="geekblue">{playing.city}</Tag>}
              {playing.tags?.map((t) => <Tag key={t} color="green">{t}</Tag>)}
            </Space>
          </Space>
        )}
      </Modal>
      <Modal
        open={!!previewing}
        title={previewing?.filename}
        footer={null}
        width={920}
        onCancel={() => setPreviewing(null)}
      >
        {previewing && (
          <img src={mediaApi.fileUrl(previewing.id)} style={{ width: '100%', maxHeight: '70vh', objectFit: 'contain' }} />
        )}
      </Modal>

      <Modal
        open={fixOpen}
        title={`修复拍摄时间（已选 ${selectedIds.size} 个文件）`}
        okText="应用"
        cancelText="取消"
        confirmLoading={fixWorking}
        okButtonProps={{ disabled: !!fixJob }}
        onOk={submitFixTime}
        onCancel={() => { if (!fixJob) setFixOpen(false) }}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {firstSelected && (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              例如「{firstSelected.filename}」当前时间：
              {firstSelected.taken_at
                ? dayjs(firstSelected.taken_at).format('YYYY-MM-DD HH:mm:ss')
                : '未知（将按修改时间计算）'}
            </Typography.Text>
          )}
          <Radio.Group value={fixMode} onChange={(e) => setFixMode(e.target.value)}>
            <Radio value="shift">整体平移（相机时钟快/慢了）</Radio>
            <Radio value="set">设为指定时间（扫描件/无时间文件）</Radio>
          </Radio.Group>
          {fixMode === 'shift' ? (
            <Space>
              <InputNumber min={-3650} max={3650} value={fixDays} onChange={(v) => setFixDays(v || 0)} />
              <span>天</span>
              <InputNumber min={-87600} max={87600} value={fixHours} onChange={(v) => setFixHours(v || 0)} />
              <span>小时</span>
              <Typography.Text type="secondary">
                合计 {fixDeltaHours >= 0 ? '+' : ''}{fixDeltaHours} 小时
              </Typography.Text>
            </Space>
          ) : (
            <DatePicker
              showTime
              value={fixSetTime}
              onChange={(v) => setFixSetTime(v)}
              placeholder="选择新的拍摄时间"
              style={{ width: 240 }}
            />
          )}
          {fixJob ? (
            <>
              <Progress status="active" size="small" />
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                正在后台修复 {fixJob.total} 个文件，完成后自动刷新
              </Typography.Text>
            </>
          ) : (
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              JPEG 照片会把新时间无损写回文件 EXIF（画质不变，后续扫描依然正确）；其他格式仅更新本工具数据库。超过 100 个文件将转后台处理。
            </Typography.Text>
          )}
        </Space>
      <FloatButton.BackTop tooltip="回到顶部" />
      </Modal>
    </Space>
  )
}
