import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Collapse,
  Input,
  Modal,
  Popconfirm,
  Radio,
  Segmented,
  Space,
  Statistic,
  Table,
  Typography,
  message,
} from 'antd'
import {
  DownloadOutlined,
  EditOutlined,
  FolderOpenOutlined,
  PlayCircleOutlined,
  SwapOutlined,
  UndoOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import FolderPicker from '../../components/FolderPicker'
import PageHeader from '../../components/PageHeader'
import { organizeApi, settingsApi } from '../../services/api'
import type { OrganizeBatch, OrganizePlan, OrganizePlanItem, OrganizeResult } from '../../types'

function formatSize(bytes: number) {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} GB`
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${(bytes / 1024).toFixed(0)} KB`
}

const FOLDER_PRESET_OPTIONS = [
  { label: '年/月', value: 'Y/M' },
  { label: '年/月/日', value: 'Y/M/D' },
  { label: '年/月/城市', value: 'Y/M/CITY' },
  { label: '年/城市', value: 'Y/CITY' },
  { label: '类别/年/月', value: 'Y/TYPE/M' },
  { label: '自定义模板', value: 'custom' },
]

const NAME_PRESET_OPTIONS = [
  { label: '统一重命名', value: 'standard' },
  { label: '保留原名', value: 'keep' },
  { label: '自定义模板', value: 'custom' },
]

export default function Organize() {
  const navigate = useNavigate()
  const [targetDir, setTargetDir] = useState('')
  const [pickerOpen, setPickerOpen] = useState(false)
  const [mode, setMode] = useState<'move' | 'copy'>('move')
  const [folderPreset, setFolderPreset] = useState('Y/M')
  const [namePreset, setNamePreset] = useState('standard')
  const [folderTemplate, setFolderTemplate] = useState('')
  const [nameTemplate, setNameTemplate] = useState('')
  const [plan, setPlan] = useState<OrganizePlan | null>(null)
  const [planning, setPlanning] = useState(false)
  const [executing, setExecuting] = useState(false)
  const [result, setResult] = useState<OrganizeResult | null>(null)
  const [emptyDirs, setEmptyDirs] = useState<string[]>([])
  const [logs, setLogs] = useState<OrganizeBatch[]>([])
  const [editingDst, setEditingDst] = useState<OrganizePlanItem | null>(null)
  const [dstInput, setDstInput] = useState('')

  const loadLogs = useCallback(() => {
    organizeApi.logs(10).then(setLogs).catch(() => {})
  }, [])

  useEffect(() => {
    settingsApi
      .get()
      .then((s) => {
        setTargetDir(s.last_target_dir)
        setMode(s.default_mode)
        setFolderPreset(s.folder_structure === 'Y/M/D' ? 'Y/M/D' : 'Y/M')
        setNamePreset(s.naming === 'keep' ? 'keep' : 'standard')
        setFolderTemplate(s.folder_template || '')
        setNameTemplate(s.name_template || '')
      })
      .catch(() => {})
    loadLogs()
  }, [loadLogs])

  const buildParams = () => ({
    target_dir: targetDir.trim(),
    mode,
    folder_structure: folderPreset === 'custom' ? 'Y/M' : folderPreset,
    naming: namePreset === 'custom' ? 'standard' : namePreset,
    folder_template: folderPreset === 'custom' ? folderTemplate : '',
    name_template: namePreset === 'custom' ? nameTemplate : '',
  })

  const generatePlan = async () => {
    if (!targetDir.trim()) {
      message.warning('请先选择目标目录')
      return
    }
    if (folderPreset === 'custom' && !folderTemplate.trim()) {
      message.warning('请填写目录模板，如 {year}/{month}/{city}')
      return
    }
    if (namePreset === 'custom' && !nameTemplate.trim()) {
      message.warning('请填写文件名模板，如 {prefix}_{datetime}')
      return
    }
    setPlanning(true)
    setResult(null)
    try {
      const p = await organizeApi.plan(buildParams())
      setPlan(p)
    } catch (e: any) {
      message.error(e.response?.data?.detail || '生成计划失败')
    } finally {
      setPlanning(false)
    }
  }

  const toggleExclude = async (item: OrganizePlanItem, checked: boolean) => {
    if (!plan) return
    // 本地立即生效，再同步后端
    const nextExcluded = new Set(plan.items.filter((i) => i.excluded).map((i) => i.media_id))
    if (checked) nextExcluded.add(item.media_id)
    else nextExcluded.delete(item.media_id)
    setPlan({
      ...plan,
      items: plan.items.map((i) => (i.media_id === item.media_id ? { ...i, excluded: checked } : i)),
    })
    try {
      await organizeApi.patchPlan(plan.plan_id, { excluded_ids: [...nextExcluded] })
    } catch (e: any) {
      message.error(e.response?.data?.detail || '保存排除项失败')
    }
  }

  const saveDst = async () => {
    if (!plan || !editingDst) return
    try {
      const p = await organizeApi.patchPlan(plan.plan_id, {
        dst_overrides: { [editingDst.media_id]: dstInput },
      })
      setPlan(p)
      setEditingDst(null)
      message.success('目标路径已更新')
    } catch (e: any) {
      message.error(e.response?.data?.detail || '更新失败')
    }
  }

  const execute = () => {
    if (!plan) return
    const toRun = plan.items.filter((i) => !i.excluded && i.action !== 'skip')
    Modal.confirm({
      title: '确认执行整理？',
      content:
        mode === 'move'
          ? `选中的 ${toRun.length} 个文件将被移动到目标目录，原位置不再保留。`
          : `选中的 ${toRun.length} 个文件将被复制到目标目录，原文件保持不变。`,
      okText: '执行',
      cancelText: '再想想',
      onOk: async () => {
        setExecuting(true)
        try {
          // 移动模式下记录源目录，执行后可一键清理空文件夹
          if (mode === 'move') {
            const srcDirs = new Set(plan.items
              .filter((i) => !i.excluded && i.action !== 'skip')
              .map((i) => i.src.replace(/[\\/][^\\/]+$/, '')))
            setEmptyDirs([...srcDirs])
          } else {
            setEmptyDirs([])
          }
          const r = await organizeApi.execute(plan.plan_id)
          setResult(r)
          setPlan(null)
          loadLogs()
          message.success(`整理完成：成功 ${r.done} 个`)
        } catch (e: any) {
          message.error(e.response?.data?.detail || '执行失败')
        } finally {
          setExecuting(false)
        }
      },
    })
  }

  const undoBatch = (batch: OrganizeBatch) => {
    Modal.confirm({
      title: `撤销批次 ${batch.batch_id}？`,
      content: '移动的文件将移回原位置，复制的副本将送入回收站。',
      okText: '撤销',
      onOk: async () => {
        try {
          const r = await organizeApi.undo(batch.batch_id)
          message.success(`已撤销：移回 ${r.moved_back} 个，删除副本 ${r.copies_removed} 个${r.failed ? `，失败 ${r.failed}` : ''}`)
          loadLogs()
        } catch (e: any) {
          message.error(e.response?.data?.detail || '撤销失败')
        }
      },
    })
  }

  const activeItems = plan?.items.filter((i) => !i.excluded) ?? []
  const toMove = activeItems.filter((i) => i.action !== 'skip')
  const toSkip = activeItems.length - toMove.length

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <PageHeader title="整理归档" subtitle="先出预览计划，确认后再动手；移动的文件随时可撤销" />
      <Card title="整理设置">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Space.Compact style={{ width: '100%', maxWidth: 640 }}>
            <Input
              placeholder="目标目录，如 D:\\整理后的相册"
              value={targetDir}
              onChange={(e) => setTargetDir(e.target.value)}
            />
            <Button icon={<FolderOpenOutlined />} onClick={() => setPickerOpen(true)}>
              浏览
            </Button>
          </Space.Compact>
          <Space wrap size="large">
            <Space>
              <Typography.Text>处理方式：</Typography.Text>
              <Radio.Group value={mode} onChange={(e) => setMode(e.target.value)}>
                <Radio value="move">移动</Radio>
                <Radio value="copy">复制</Radio>
              </Radio.Group>
            </Space>
            <Space wrap>
              <Typography.Text>目录结构：</Typography.Text>
              <Segmented
                value={folderPreset}
                onChange={(v) => setFolderPreset(v as string)}
                options={FOLDER_PRESET_OPTIONS}
              />
            </Space>
            <Space wrap>
              <Typography.Text>文件名：</Typography.Text>
              <Segmented
                value={namePreset}
                onChange={(v) => setNamePreset(v as string)}
                options={NAME_PRESET_OPTIONS}
              />
            </Space>
          </Space>
          <Collapse
            ghost
            items={[
              {
                key: 'tpl',
                label: '自定义模板（可选）',
                children: (
                  <Space direction="vertical" size={4} style={{ width: '100%' }}>
                    <Input
                      placeholder="目录模板，如 {year}/{month}/{city}；可用 {year} {month} {day} {city} {category} {type}"
                      value={folderTemplate}
                      onChange={(e) => setFolderTemplate(e.target.value)}
                    />
                    <Input
                      placeholder="文件名模板，如 {prefix}_{datetime}；可用 {prefix} {datetime} {original}"
                      value={nameTemplate}
                      onChange={(e) => setNameTemplate(e.target.value)}
                    />
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      填写了模板时优先生效；城市来自照片 EXIF GPS 定位（无定位为「未知地点」），类别为「照片/截图/聊天导出」。
                    </Typography.Text>
                  </Space>
                ),
              },
            ]}
          />
          <div>
            <Button type="primary" icon={<PlayCircleOutlined />} loading={planning} onClick={generatePlan}>
              生成整理预览
            </Button>
          </div>
          <Typography.Text type="secondary">
            示例：{targetDir || '目标目录'}\2024\05\IMG_20240501_103000.jpg（模板自定义后以预览为准）
          </Typography.Text>
        </Space>
      </Card>

      {plan && (
        <Card
          title={`整理计划预览（共 ${plan.items.length} 个文件）`}
          extra={
            <Space>
              <Button onClick={() => setPlan(null)}>放弃</Button>
              <Button type="primary" icon={<SwapOutlined />} loading={executing} onClick={execute}>
                确认执行（{toMove.length} 个）
              </Button>
            </Space>
          }
        >
          <Space size="large" style={{ marginBottom: 16 }}>
            <Statistic title="将处理" value={toMove.length} suffix={`个（${formatSize(toMove.reduce((s, i) => s + i.size, 0))}）`} />
            <Statistic title="自动跳过" value={toSkip} suffix="个" />
            <Statistic title="已排除" value={plan.items.length - activeItems.length} suffix="个" />
          </Space>
          <Table
            size="small"
            rowKey="media_id"
            pagination={{ pageSize: 20, showSizeChanger: false }}
            dataSource={plan.items}
            columns={[
              {
                title: '整理',
                width: 60,
                render: (_: unknown, record) => (
                  <Checkbox
                    checked={!record.excluded}
                    onChange={(e) => toggleExclude(record, !e.target.checked)}
                  />
                ),
              },
              { title: '文件名', dataIndex: 'filename', ellipsis: true },
              {
                title: '类型',
                dataIndex: 'media_type',
                width: 70,
                render: (t: string) => (t === 'photo' ? '照片' : '视频'),
              },
              { title: '源路径', dataIndex: 'src', ellipsis: true },
              {
                title: '目标路径',
                dataIndex: 'dst',
                ellipsis: true,
                render: (dst: string, record) =>
                  record.action === 'skip' ? (
                    <Typography.Text type="secondary" delete>{dst}</Typography.Text>
                  ) : (
                    <Space size={4}>
                      <Typography.Text style={{ color: record.excluded ? undefined : '#1677ff' }}>{dst}</Typography.Text>
                      <Button
                        size="small"
                        type="text"
                        icon={<EditOutlined />}
                        onClick={() => {
                          setEditingDst(record)
                          setDstInput(record.dst)
                        }}
                      />
                    </Space>
                  ),
              },
              {
                title: '动作',
                dataIndex: 'action',
                width: 110,
                render: (a: string, record) => (
                  <Typography.Text type={a === 'skip' ? 'secondary' : undefined}>
                    {record.excluded ? '已排除' : a === 'move' ? '移动' : a === 'copy' ? '复制' : '跳过'}
                    {record.note ? `（${record.note}）` : ''}
                  </Typography.Text>
                ),
              },
            ]}
          />
        </Card>
      )}

      {result && (
        <Alert
          type={result.failed > 0 ? 'warning' : 'success'}
          showIcon
          message={`整理完成：成功 ${result.done}，跳过 ${result.skipped}，失败 ${result.failed}`}
          description={
            <Space direction="vertical" size={4}>
              <Space wrap>
                {result.failed > 0 ? <span>部分文件处理失败，可在整理历史批次中查看。</span> : <span>整理后的文件已同步到媒体库。</span>}
                <Button size="small" type="link" onClick={() => navigate('/gallery')}>去照片墙查看 →</Button>
              </Space>
              {emptyDirs.length > 0 && (
                <Space wrap>
                  <span>源目录可能已腾空，是否清理空文件夹？</span>
                  <Button
                    size="small"
                    onClick={async () => {
                      try {
                        const r = await organizeApi.cleanEmpty(emptyDirs)
                        message.success(`已清理 ${r.removed} 个空文件夹`)
                        setEmptyDirs([])
                      } catch (e: any) {
                        message.error(e.response?.data?.detail || '清理失败')
                      }
                    }}
                  >
                    清理 {emptyDirs.length} 个源目录的空文件夹
                  </Button>
                </Space>
              )}
            </Space>
          }
        />
      )}

      <Card title="整理历史">
        {logs.length === 0 ? (
          <Typography.Text type="secondary">还没有整理记录。</Typography.Text>
        ) : (
          <Table
            size="small"
            rowKey="batch_id"
            pagination={false}
            dataSource={logs}
            columns={[
              { title: '批次', dataIndex: 'batch_id' },
              { title: '时间', dataIndex: 'created_at', render: (t: string) => new Date(t).toLocaleString('zh-CN') },
              {
                title: '动作',
                dataIndex: 'action',
                render: (a: string) => {
                  if (a.startsWith('undo-') || a.startsWith('undo_')) return '撤销'
                  const labels: Record<string, string> = {
                    move: '移动', copy: '复制', skip: '跳过', delete: '删除',
                    trash: '移入回收站', move_duplicate: '移入重复文件夹',
                  }
                  return labels[a] ?? a
                },
              },
              { title: '成功', dataIndex: 'done' },
              { title: '跳过', dataIndex: 'skipped' },
              { title: '失败', dataIndex: 'failed', render: (v: number) => (v > 0 ? <Typography.Text type="danger">{v}</Typography.Text> : v) },
              {
                title: '操作',
                key: 'ops',
                render: (_: unknown, record) => (
                  <Space size={4}>
                    {!record.undone && record.done > 0 && !record.batch_id.startsWith('undo-') && (
                      <Popconfirm title="移动的文件将移回原位，副本送回收站，确认撤销？" onConfirm={() => undoBatch(record)}>
                        <Button size="small" icon={<UndoOutlined />}>撤销</Button>
                      </Popconfirm>
                    )}
                    <Button size="small" icon={<DownloadOutlined />} href={organizeApi.exportCsvUrl(record.batch_id)}>
                      导出
                    </Button>
                  </Space>
                ),
              },
            ]}
          />
        )}
      </Card>

      <FolderPicker
        open={pickerOpen}
        title="选择目标目录"
        initialDir={targetDir}
        onCancel={() => setPickerOpen(false)}
        onOk={(dir) => {
          setTargetDir(dir)
          setPickerOpen(false)
        }}
      />

      <Modal
        open={!!editingDst}
        title={`修改目标路径：${editingDst?.filename ?? ''}`}
        onOk={saveDst}
        onCancel={() => setEditingDst(null)}
        width={640}
      >
        <Input value={dstInput} onChange={(e) => setDstInput(e.target.value)} />
      </Modal>
    </Space>
  )
}
