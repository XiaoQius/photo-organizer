import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Empty,
  Image as AntImage,
  Input,
  Modal,
  Radio,
  Segmented,
  Space,
  Spin,
  Tag,
  Typography,
  message,
} from 'antd'
import { DeleteOutlined, SearchOutlined, SwapOutlined } from '@ant-design/icons'
import PageHeader from '../../components/PageHeader'
import { duplicatesApi, mediaApi } from '../../services/api'
import type { DuplicateGroup, MediaFile } from '../../types'

function formatSize(bytes: number) {
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${(bytes / 1024).toFixed(0)} KB`
}

const QUALITY_LABELS: Record<string, string> = {
  blurry: '模糊',
  dark: '过暗',
  bright: '过曝',
}

type TabKey = 'duplicates' | 'quality' | 'screenshots'

/** 清理中心：重复文件 / 疑似废片 / 截图与聊天导出，全部支持自由勾选清理 */
export default function Duplicates() {
  const [tab, setTab] = useState<TabKey>('duplicates')
  const [groups, setGroups] = useState<DuplicateGroup[]>([])
  // 重复页签：自由勾选要删除的文件（不再限制每组必须保留一个）
  const [dupSelected, setDupSelected] = useState<Set<number>>(new Set())
  const [flagged, setFlagged] = useState<MediaFile[]>([])
  const [shots, setShots] = useState<MediaFile[]>([])
  const [shotKind, setShotKind] = useState<'screenshot' | 'chat_export'>('screenshot')
  const [loading, setLoading] = useState(false)
  const [action, setAction] = useState<'move' | 'trash'>('move')
  const [working, setWorking] = useState(false)
  const [kind, setKind] = useState<'all' | 'exact' | 'similar'>('all')
  // 选择状态（废片/截图页）
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [moveDir, setMoveDir] = useState('')

  const loadDuplicates = useCallback(() => {
    setLoading(true)
    duplicatesApi
      .groups()
      .then((r) => {
        setGroups([...r.exact, ...r.similar])
        setDupSelected(new Set())
      })
      .catch((e) => message.error(e.response?.data?.detail || '加载失败'))
      .finally(() => setLoading(false))
  }, [])

  const loadFlagged = useCallback(() => {
    setLoading(true)
    mediaApi.list({ page: 1, page_size: 200, quality: 'flagged' })
      .then((r) => setFlagged(r.items))
      .catch((e) => message.error(e.response?.data?.detail || '加载失败'))
      .finally(() => setLoading(false))
  }, [])

  const loadShots = useCallback(() => {
    setLoading(true)
    mediaApi.list({ page: 1, page_size: 500, category: shotKind })
      .then((r) => setShots(r.items))
      .catch((e) => message.error(e.response?.data?.detail || '加载失败'))
      .finally(() => setLoading(false))
  }, [shotKind])

  useEffect(() => {
    setSelectedIds(new Set())
    if (tab === 'duplicates') loadDuplicates()
    else if (tab === 'quality') loadFlagged()
    else loadShots()
  }, [tab, loadDuplicates, loadFlagged, loadShots])

  const visible = groups.filter((g) => kind === 'all' || g.kind === kind)
  const visibleIds = new Set(visible.flatMap((g) => g.files.map((f) => f.id)))
  const dupRemoveIds = [...dupSelected].filter((id) => visibleIds.has(id))
  const dupRemovableSize = visible
    .flatMap((g) => g.files)
    .filter((f) => dupSelected.has(f.id))
    .reduce((s, f) => s + f.size, 0)
  const cleanTargets = tab === 'quality' ? flagged : shots
  const cleanSelected = cleanTargets.filter((f) => selectedIds.has(f.id))
  const cleanSelectedSize = cleanSelected.reduce((s, f) => s + f.size, 0)

  const toggleDupSelect = (id: number) => {
    setDupSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const preselectDuplicates = () => {
    // 采纳推荐：每组保留推荐项（最高清），其余勾选为待删除
    setDupSelected(new Set(
      visible.flatMap((g) => g.files.filter((f) => f.id !== g.recommended_id).map((f) => f.id)),
    ))
  }

  const runDuplicatesResolve = () => {
    if (dupRemoveIds.length === 0) {
      message.warning('请先勾选要处理的文件')
      return
    }
    const content =
      action === 'move'
        ? '勾选的文件将被移动到各自原目录下的「重复文件」文件夹，确认后可手动处理。'
        : '勾选的文件将被送入系统回收站，可在回收站还原。'
    Modal.confirm({
      title: action === 'move' ? '确认移入重复文件夹？' : '确认送入回收站？',
      content,
      okText: action === 'move' ? '移入重复文件夹' : '送入回收站',
      okButtonProps: action === 'trash' ? { danger: true } : {},
      onOk: async () => {
        setWorking(true)
        try {
          const r = await duplicatesApi.resolve({
            keep_ids: [...visibleIds].filter((id) => !dupSelected.has(id)),
            remove_ids: dupRemoveIds,
            action,
            confirm_trash: action === 'trash',
          })
          message.success(`处理完成：成功 ${r.done} 个${r.failed ? `，失败 ${r.failed} 个` : ''}`)
          loadDuplicates()
        } catch (e: any) {
          message.error(e.response?.data?.detail || '处理失败')
        } finally {
          setWorking(false)
        }
      },
    })
  }

  const runCleanup = (cleanupAction: 'trash' | 'move') => {
    if (selectedIds.size === 0) {
      message.warning('请先点选要处理的文件')
      return
    }
    if (cleanupAction === 'trash') {
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

  const doCleanup = async (cleanupAction: 'trash' | 'move') => {
    setWorking(true)
    try {
      const r = await mediaApi.cleanup({
        ids: [...selectedIds],
        action: cleanupAction,
        target_dir: moveDir.trim(),
        confirm_trash: cleanupAction === 'trash',
      })
      message.success(`处理完成：成功 ${r.done} 个${r.failed ? `，失败 ${r.failed} 个` : ''}`)
      setSelectedIds(new Set())
      if (tab === 'quality') loadFlagged()
      else loadShots()
    } catch (e: any) {
      message.error(e.response?.data?.detail || '处理失败')
    } finally {
      setWorking(false)
    }
  }

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <PageHeader title="清理中心" subtitle="重复文件、废片、截图，自由勾选，默认进回收站不直接删" />
      <Card
        title="清理中心"
        extra={tab === 'duplicates' ? (
          <Button icon={<SearchOutlined />} onClick={loadDuplicates} loading={loading}>
            重新检测
          </Button>
        ) : (
          <Button onClick={tab === 'quality' ? loadFlagged : loadShots} loading={loading}>
            刷新
          </Button>
        )}
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Segmented
            value={tab}
            onChange={(v) => setTab(v as TabKey)}
            options={[
              { label: '重复文件', value: 'duplicates' },
              { label: '疑似废片', value: 'quality' },
              { label: '截图与导出', value: 'screenshots' },
            ]}
          />

          {tab === 'duplicates' && (
            <>
              <Space wrap size="large">
                <Space>
                  <Typography.Text>显示：</Typography.Text>
                  <Radio.Group value={kind} onChange={(e) => setKind(e.target.value)}>
                    <Radio.Button value="all">全部（{groups.length}）</Radio.Button>
                    <Radio.Button value="exact">
                      完全相同（{groups.filter((g) => g.kind === 'exact').length}）
                    </Radio.Button>
                    <Radio.Button value="similar">
                      相似（{groups.filter((g) => g.kind === 'similar').length}）
                    </Radio.Button>
                  </Radio.Group>
                </Space>
                <Space>
                  <Typography.Text>处理方式：</Typography.Text>
                  <Radio.Group value={action} onChange={(e) => setAction(e.target.value)}>
                    <Radio value="move">移入重复文件夹</Radio>
                    <Radio value="trash">送入回收站</Radio>
                  </Radio.Group>
                </Space>
                <Button size="small" onClick={preselectDuplicates} disabled={visible.length === 0}>
                  全部采纳推荐
                </Button>
                <Button size="small" onClick={() => setDupSelected(new Set())} disabled={dupSelected.size === 0}>
                  清空选择
                </Button>
                <Button
                  type="primary"
                  danger={action === 'trash'}
                  icon={action === 'move' ? <SwapOutlined /> : <DeleteOutlined />}
                  disabled={dupRemoveIds.length === 0}
                  loading={working}
                  onClick={runDuplicatesResolve}
                >
                  处理 {dupRemoveIds.length} 个（省 {formatSize(dupRemovableSize)}）
                </Button>
              </Space>
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                每组会推荐保留最清晰的一张（照片按像素数、视频按体积，标「推荐保留」）；点「全部采纳推荐」一键勾掉其余文件，也可自由勾选。
              </Typography.Text>
              {groups.some((g) => g.kind === 'similar') && (
                <Alert
                  type="info"
                  showIcon
                  message="「相似」通过感知哈希识别：图片为整图 dHash，视频为三帧指纹（需 ffmpeg）。内容不完全相同，处理前请仔细确认。"
                />
              )}
            </>
          )}

          {tab === 'quality' && (
            <Space wrap size="large">
              <Typography.Text type="secondary">
                模糊/过暗/过曝照片由扫描时自动检测（拉普拉斯方差 + 亮度均值），移动到待清理文件夹或送入回收站前请逐张确认。
              </Typography.Text>
              <Button danger icon={<DeleteOutlined />} disabled={selectedIds.size === 0} loading={working}
                      onClick={() => runCleanup('trash')}>
                送入回收站（{selectedIds.size}）
              </Button>
              <Input
                placeholder="或移动到指定文件夹（留空则移到原目录下「待清理」）"
                style={{ width: 320 }}
                value={moveDir}
                onChange={(e) => setMoveDir(e.target.value)}
              />
              <Button icon={<SwapOutlined />} disabled={selectedIds.size === 0} loading={working}
                      onClick={() => runCleanup('move')}>
                移动
              </Button>
            </Space>
          )}

          {tab === 'screenshots' && (
            <Space wrap size="large">
              <Radio.Group value={shotKind} onChange={(e) => setShotKind(e.target.value)}>
                <Radio.Button value="screenshot">截图</Radio.Button>
                <Radio.Button value="chat_export">聊天导出</Radio.Button>
              </Radio.Group>
              <Button danger icon={<DeleteOutlined />} disabled={selectedIds.size === 0} loading={working}
                      onClick={() => runCleanup('trash')}>
                送入回收站（{selectedIds.size}）
              </Button>
              <Input
                placeholder="或移动到指定文件夹（留空则移到原目录下「待清理」）"
                style={{ width: 320 }}
                value={moveDir}
                onChange={(e) => setMoveDir(e.target.value)}
              />
              <Button icon={<SwapOutlined />} disabled={selectedIds.size === 0} loading={working}
                      onClick={() => runCleanup('move')}>
                移动
              </Button>
            </Space>
          )}
        </Space>
      </Card>

      <Spin spinning={loading}>
        {tab === 'duplicates' && (
          visible.length === 0 && !loading ? (
            <Empty description="没有检测到重复文件" style={{ marginTop: 80 }} />
          ) : (
            visible.map((g) => (
              <Card
                key={g.key}
                size="small"
                style={{ marginBottom: 12 }}
                title={
                  <Space>
                    <Tag color={g.kind === 'exact' ? 'red' : 'orange'}>
                      {g.kind === 'exact' ? '完全相同' : '相似'}
                    </Tag>
                    <Typography.Text type="secondary">
                      {g.files.length} 个文件 · 点击勾选要删除的文件
                    </Typography.Text>
                    <Button
                      size="small"
                      type="link"
                      onClick={() => setDupSelected((prev) => {
                        const next = new Set(prev)
                        g.files.forEach((f) => {
                          if (f.id === g.recommended_id) next.delete(f.id)
                          else next.add(f.id)
                        })
                        return next
                      })}
                    >
                      本组采纳推荐
                    </Button>
                  </Space>
                }
              >
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))',
                    gap: 12,
                  }}
                >
                  {g.files.map((f) => (
                    <FileCard
                      key={f.id}
                      file={f}
                      selected={dupSelected.has(f.id)}
                      selectionLabel={dupSelected.has(f.id) ? '待删除' : undefined}
                      dangerSelected={dupSelected.has(f.id)}
                      recommended={f.id === g.recommended_id}
                      onClick={() => toggleDupSelect(f.id)}
                    />
                  ))}
                </div>
              </Card>
            ))
          )
        )}

        {tab !== 'duplicates' && (
          cleanTargets.length === 0 && !loading ? (
            <Empty description={tab === 'quality' ? '没有疑似废片' : '没有截图或聊天导出文件'} style={{ marginTop: 80 }} />
          ) : (
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))',
                gap: 12,
              }}
            >
              {cleanTargets.map((f) => (
                <FileCard
                  key={f.id}
                  file={f}
                  selected={selectedIds.has(f.id)}
                  selectionLabel="已选"
                  onClick={() => toggleSelect(f.id)}
                  showBadges
                />
              ))}
            </div>
          )
        )}
      </Spin>
    </Space>
  )
}

function FileCard({ file, selected, selectionLabel, onClick, showBadges, dangerSelected, recommended }: {
  file: MediaFile
  selected: boolean
  selectionLabel?: string
  onClick: () => void
  showBadges?: boolean
  dangerSelected?: boolean
  recommended?: boolean
}) {
  return (
    <div
      onClick={onClick}
      style={{
        cursor: 'pointer',
        borderRadius: 8,
        overflow: 'hidden',
        border: selected ? (dangerSelected ? '2px solid #ff4d4f' : '2px solid #52c41a') : '2px solid #f0f0f0',
        position: 'relative',
      }}
    >
      <div style={{ background: '#fafafa', aspectRatio: '1' }}>
        {file.media_type === 'photo' ? (
          <AntImage
            src={mediaApi.thumbnailUrl(file.id)}
            width="100%"
            height="100%"
            style={{ objectFit: 'cover' }}
            preview={{ src: mediaApi.fileUrl(file.id) }}
          />
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
            <Typography.Text type="secondary">视频 · {formatSize(file.size)}</Typography.Text>
          </div>
        )}
      </div>
      <div style={{ padding: '6px 8px', fontSize: 12 }}>
        <div style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {file.filename}
        </div>
        <Typography.Text type="secondary">
          {formatSize(file.size)} · {new Date(file.taken_at || file.mtime * 1000).toLocaleDateString('zh-CN')}
          {file.width && file.height ? ` · ${file.width}×${file.height}` : ''}
        </Typography.Text>
        {showBadges && (
          <div style={{ marginTop: 2 }}>
            {file.quality_flag && <Tag color="red">{QUALITY_LABELS[file.quality_flag]}</Tag>}
            {file.city && <Tag color="geekblue">{file.city}</Tag>}
          </div>
        )}
      </div>
      {selected && selectionLabel && (
        <Tag color={dangerSelected ? 'error' : 'success'} style={{ position: 'absolute', top: 6, left: 6 }}>
          {selectionLabel}
        </Tag>
      )}
      {recommended && !selected && (
        <Tag color="warning" style={{ position: 'absolute', top: 6, right: 6 }}>推荐保留</Tag>
      )}
    </div>
  )
}
