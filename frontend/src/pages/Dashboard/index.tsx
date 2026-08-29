import { useCallback, useEffect, useRef, useState } from 'react'
import {
  Button,
  Card,
  Checkbox,
  Col,
  Input,
  Modal,
  Progress,
  Row,
  Space,
  Statistic,
  Tag,
  Typography,
  message,
} from 'antd'
import {
  ScanOutlined,
  FileTextOutlined,
  FileZipOutlined,
  FolderOpenOutlined,
  PictureOutlined,
  SoundOutlined,
  VideoCameraOutlined,
  CopyOutlined,
  StopOutlined,
  SafetyCertificateOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import FolderPicker from '../../components/FolderPicker'
import PageHeader from '../../components/PageHeader'
import { jobsApi, mediaApi, scanApi, settingsApi, statsApi } from '../../services/api'
import type { BackgroundJob, ScanJob, StatsOverview } from '../../types'

const SOURCE_TAG: Record<string, { text: string; color: string }> = {
  exif: { text: 'EXIF 拍摄时间', color: 'green' },
  video: { text: '视频元数据', color: 'blue' },
  filename: { text: '文件名日期', color: 'orange' },
  mtime: { text: '修改时间', color: 'default' },
}

function StatLink({ to, title, children }: { to: string; title: string; children: React.ReactNode }) {
  const navigate = useNavigate()
  return (
    <div
      onClick={() => navigate(to)}
      title={title}
      style={{ cursor: 'pointer', borderRadius: 10, padding: '4px 8px', margin: '-4px -8px', transition: 'background 0.15s' }}
      onMouseEnter={(e) => (e.currentTarget.style.background = '#eef0f4')}
      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
    >
      {children}
    </div>
  )
}

function formatSize(bytes: number) {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} GB`
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${(bytes / 1024).toFixed(0)} KB`
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [sourceDir, setSourceDir] = useState('')
  const [pickerOpen, setPickerOpen] = useState(false)
  const [job, setJob] = useState<ScanJob | null>(null)
  const [stats, setStats] = useState<StatsOverview | null>(null)
  const [starting, setStarting] = useState(false)
  const [qualityJob, setQualityJob] = useState<BackgroundJob | null>(null)
  const [heicCount, setHeicCount] = useState(0)
  const [scanDocs, setScanDocs] = useState(false)
  const [scanAudio, setScanAudio] = useState(false)
  const [scanArchives, setScanArchives] = useState(false)
  const timerRef = useRef<number | null>(null)
  const qualityTimer = useRef<number | null>(null)

  const loadStats = useCallback(() => {
    statsApi.overview().then(setStats).catch(() => {})
  }, [])

  useEffect(() => {
    loadStats()
    settingsApi
      .get()
      .then((s) => {
        setSourceDir(s.last_source_dir)
        setScanDocs(s.scan_docs === '1')
        setScanAudio(s.scan_audio === '1')
        setScanArchives(s.scan_archives === '1')
      })
      .catch(() => {})
    mediaApi.heic().then((r) => setHeicCount(r.count)).catch(() => {})
  }, [loadStats])

  // 质检进度轮询
  useEffect(() => {
    if (qualityJob?.status === 'running' && qualityJob.job_id) {
      qualityTimer.current = window.setInterval(() => {
        jobsApi.status(qualityJob.job_id).then((res) => {
          setQualityJob(res)
          if (res.status !== 'running') {
            loadStats()
            message.success(`质检完成，发现 ${res.result?.flagged ?? 0} 张疑似废片`)
          }
        }).catch(() => {})
      }, 1000)
    }
    return () => {
      if (qualityTimer.current) window.clearInterval(qualityTimer.current)
    }
  }, [qualityJob?.job_id, qualityJob?.status, loadStats])

  const startQuality = async () => {
    try {
      const r = await mediaApi.analyze()
      if (!r.job_id) {
        message.info('所有照片都已完成质检')
        return
      }
      setQualityJob({ job_id: r.job_id, status: 'running', total: r.pending, processed: 0, current: '', result: {}, error: '', kind: 'quality', label: '' })
    } catch (e: any) {
      message.error(e.response?.data?.detail || '启动质检失败')
    }
  }

  const startConvert = () => {
    mediaApi.heic().then((r) => {
      if (r.count === 0) {
        message.info('没有 HEIC 文件')
        return
      }
      Modal.confirm({
        title: `将 ${r.count} 个 HEIC 转换为 JPG？`,
        content: '会在原文件旁边生成同名 JPG（原 HEIC 保留），需要已安装 pillow-heif。',
        onOk: async () => {
          try {
            const { job_id } = await mediaApi.convert(r.items.map((m) => m.id))
            Modal.info({
              title: '转换已开始',
              content: '转换在后台进行，完成后重新扫描目录即可看到 JPG 文件。',
            })
            void job_id
          } catch (e: any) {
            message.error(e.response?.data?.detail || '启动转换失败')
          }
        },
      })
    })
  }

  const purgeMissing = () => {
    Modal.confirm({
      title: '清理失效记录？',
      content: '将删除数据库中「文件已不在磁盘上」的记录，不会删除任何文件。',
      onOk: async () => {
        try {
          const r = await mediaApi.purgeMissing()
          message.success(`已清理 ${r.removed} 条失效记录`)
          loadStats()
        } catch (e: any) {
          message.error(e.response?.data?.detail || '清理失败')
        }
      },
    })
  }

  // 轮询扫描进度
  useEffect(() => {
    if (job?.status === 'running' && job.job_id) {
      timerRef.current = window.setInterval(() => {
        scanApi.status(job.job_id).then((res) => {
          setJob(res)
          if (res.status !== 'running') loadStats()
        }).catch(() => {})
      }, 800)
    }
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current)
    }
  }, [job?.job_id, job?.status, loadStats])

  const startScan = async () => {
    if (!sourceDir.trim()) {
      message.warning('请先选择要扫描的目录')
      return
    }
    setStarting(true)
    try {
      // 保存扫描范围开关，扫描线程按设置决定包含哪些文件类型
      await settingsApi.update({
        scan_docs: scanDocs ? '1' : '0',
        scan_audio: scanAudio ? '1' : '0',
        scan_archives: scanArchives ? '1' : '0',
      })
      const { job_id } = await scanApi.start(sourceDir.trim())
      message.success('扫描已开始')
      setJob({ job_id, status: 'running', total: 0, processed: 0, current_file: '', added: 0, updated: 0, skipped: 0, error: '' })
    } catch (e: any) {
      message.error(e.response?.data?.detail || '启动扫描失败')
    } finally {
      setStarting(false)
    }
  }

  const percent = job && job.total > 0 ? Math.round((job.processed / job.total) * 100) : 0

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <PageHeader title="工作台" subtitle="扫描目录、掌握照片视频的整体情况，所有整理操作都有预览和后路" />
      <Card title="扫描媒体文件">
        <Space.Compact style={{ width: '100%', maxWidth: 720 }}>
          <Input
            placeholder="选择要整理的照片视频目录，如 D:\\相册"
            value={sourceDir}
            onChange={(e) => setSourceDir(e.target.value)}
            onPressEnter={startScan}
          />
          <Button icon={<FolderOpenOutlined />} onClick={() => setPickerOpen(true)}>
            浏览
          </Button>
          <Button type="primary" icon={<ScanOutlined />} loading={starting} onClick={startScan}>
            开始扫描
          </Button>
        </Space.Compact>
        <Space wrap style={{ marginTop: 12 }}>
          <Typography.Text type="secondary">扫描范围：</Typography.Text>
          <Checkbox checked={scanDocs} onChange={(e) => setScanDocs(e.target.checked)}>文档（pdf/office/文本等）</Checkbox>
          <Checkbox checked={scanAudio} onChange={(e) => setScanAudio(e.target.checked)}>音频（mp3/flac 等）</Checkbox>
          <Checkbox checked={scanArchives} onChange={(e) => setScanArchives(e.target.checked)}>压缩包（zip/rar 等）</Checkbox>
          <Typography.Text type="secondary">照片和视频始终包含</Typography.Text>
        </Space>
        <Typography.Text type="secondary" style={{ display: 'block', marginTop: 8 }}>
          扫描会读取拍摄时间（EXIF / 视频元数据 / 文件名日期 / 修改时间）、计算重复检测哈希，文件不会被移动或修改。
        </Typography.Text>
      </Card>

      {job && job.status !== 'none' && (
        <Card title="扫描进度" extra={job.status === 'running' && (
          <Button size="small" icon={<StopOutlined />} onClick={() => scanApi.cancel(job.job_id).then(() => message.info('正在取消…'))}>
            取消
          </Button>
        )}>
          {job.status === 'running' ? (
            <>
              <Progress percent={percent} status="active" />
              <Typography.Text type="secondary" style={{ fontSize: 12, wordBreak: 'break-all' }}>
                正在处理：{job.current_file || '…'}（{job.processed}/{job.total || '?'}）
              </Typography.Text>
            </>
          ) : (
            <Space wrap>
              <Tag color={job.status === 'done' ? 'green' : job.status === 'error' ? 'red' : 'default'}>
                {job.status === 'done' ? '扫描完成' : job.status === 'cancelled' ? '已取消' : `出错：${job.error}`}
              </Tag>
              <Statistic className="stat-modern" title="新增" value={job.added} />
              <Statistic className="stat-modern" title="更新" value={job.updated} />
              <Statistic className="stat-modern" title="跳过（未变化）" value={job.skipped} />
            </Space>
          )}
        </Card>
      )}

      <Card title="媒体库总览" extra={<Button type="link" onClick={() => navigate('/gallery')}>去照片墙浏览 →</Button>}>
        {stats ? (
          <>
            <Row gutter={16}>
              <Col span={6}><Statistic className="stat-modern" title="文件总数" value={stats.total_count} /></Col>
              <Col span={6}><Statistic className="stat-modern" title="总大小" value={formatSize(stats.total_size)} /></Col>
              <Col span={6}>
                <StatLink to="/gallery?type=photo" title="点击查看全部照片">
                  <Statistic className="stat-modern" title="照片" value={stats.photo_count} suffix={`（${formatSize(stats.photo_size)}）`} prefix={<PictureOutlined />} />
                </StatLink>
              </Col>
              <Col span={6}>
                <StatLink to="/gallery?type=video" title="点击查看全部视频">
                  <Statistic className="stat-modern" title="视频" value={stats.video_count} suffix={`（${formatSize(stats.video_size)}）`} prefix={<VideoCameraOutlined />} />
                </StatLink>
              </Col>
            </Row>
            <Row gutter={16} style={{ marginTop: 24 }}>
              <Col span={6}>
                <StatLink to="/gallery?type=doc" title="点击查看全部文档">
                  <Statistic className="stat-modern" title="文档" value={stats.doc_count} suffix={`（${formatSize(stats.doc_size)}）`} prefix={<FileTextOutlined />} />
                </StatLink>
              </Col>
              <Col span={6}>
                <StatLink to="/gallery?type=audio" title="点击查看全部音频">
                  <Statistic className="stat-modern" title="音频" value={stats.audio_count} suffix={`（${formatSize(stats.audio_size)}）`} prefix={<SoundOutlined />} />
                </StatLink>
              </Col>
              <Col span={6}>
                <StatLink to="/gallery?type=archive" title="点击查看全部压缩包">
                  <Statistic className="stat-modern" title="压缩包" value={stats.archive_count} suffix={`（${formatSize(stats.archive_size)}）`} prefix={<FileZipOutlined />} />
                </StatLink>
              </Col>
              <Col span={6}><Statistic className="stat-modern" title="未能确定拍摄时间" value={stats.no_date_count} /></Col>
            </Row>
            <Row gutter={16} style={{ marginTop: 24 }}>
              <Col span={6}><Statistic className="stat-modern" title="疑似重复文件" value={stats.duplicate_count} prefix={<CopyOutlined />} /></Col>
              <Col span={6}>
                <StatLink to="/gallery?quality=flagged" title="点击查看疑似废片">
                  <Statistic className="stat-modern" title="疑似废片" value={stats.flagged_count} prefix={<SafetyCertificateOutlined />} />
                </StatLink>
              </Col>
              <Col span={6}>
                <StatLink to="/gallery?category=screenshot" title="点击查看截图（在照片墙中可切换聊天导出）">
                  <Statistic className="stat-modern" title="截图 / 聊天导出" value={stats.screenshot_count} suffix={`/ ${stats.chat_export_count}`} />
                </StatLink>
              </Col>
              <Col span={6}><Statistic className="stat-modern" title="已识别地点" value={stats.located_count} /></Col>
            </Row>
            <Space wrap style={{ marginTop: 16 }}>
              <Button size="small" loading={qualityJob?.status === 'running'} onClick={startQuality}>
                {qualityJob?.status === 'running' ? `质检中 ${qualityJob.processed}/${qualityJob.total}` : '运行废片质检'}
              </Button>
              {heicCount > 0 && (
                <Button size="small" onClick={startConvert}>HEIC 转 JPG（{heicCount} 个）</Button>
              )}
              <Button size="small" onClick={purgeMissing}>清理失效记录</Button>
              <Button size="small" type="link" onClick={() => navigate('/duplicates')}>去清理中心 →</Button>
            </Space>
            {qualityJob?.status === 'running' && (
              <Progress percent={qualityJob.total ? Math.round((qualityJob.processed / qualityJob.total) * 100) : 0}
                        size="small" status="active" style={{ maxWidth: 480, marginTop: 8 }} />
            )}
          </>
        ) : (
          <Typography.Text type="secondary">还没有数据，先扫描一个目录吧。</Typography.Text>
        )}
      </Card>

      <FolderPicker
        open={pickerOpen}
        title="选择要扫描的目录"
        initialDir={sourceDir}
        onCancel={() => setPickerOpen(false)}
        onOk={(dir) => {
          setSourceDir(dir)
          setPickerOpen(false)
        }}
      />
    </Space>
  )
}
