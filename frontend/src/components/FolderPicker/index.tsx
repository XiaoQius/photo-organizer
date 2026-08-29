import { useEffect, useState } from 'react'
import { Breadcrumb, Button, Empty, List, Modal, Space, Typography, message } from 'antd'
import { ArrowUpOutlined, FolderOutlined } from '@ant-design/icons'
import { fsApi } from '../../services/api'

interface Props {
  open: boolean
  title: string
  initialDir?: string
  onCancel: () => void
  onOk: (dir: string) => void
}

/** 本机目录选择弹窗：通过后端浏览文件系统，选择一个文件夹 */
export default function FolderPicker({ open, title, initialDir, onCancel, onOk }: Props) {
  const [current, setCurrent] = useState('')
  const [dirs, setDirs] = useState<string[]>([])
  const [parent, setParent] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const load = (path: string) => {
    setLoading(true)
    fsApi
      .list(path)
      .then((res) => {
        setCurrent(res.path)
        setDirs(res.directories)
        setParent(res.parent)
      })
      .catch((e) => message.error(e.response?.data?.detail || '读取目录失败'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    if (open) load(initialDir || '')
  }, [open, initialDir])

  const name = (p: string) => p.split(/[\\/]/).filter(Boolean).pop() || p

  return (
    <Modal
      open={open}
      title={title}
      width={560}
      onCancel={onCancel}
      footer={[
        <Button key="cancel" onClick={onCancel}>
          取消
        </Button>,
        <Button key="ok" type="primary" disabled={!current} onClick={() => onOk(current)}>
          选择当前目录
        </Button>,
      ]}
    >
      <Space direction="vertical" style={{ width: '100%' }} size="small">
        <Space wrap>
          <Typography.Text strong>当前：{current || '此电脑'}</Typography.Text>
          {parent !== null && (
            <Button size="small" icon={<ArrowUpOutlined />} onClick={() => load(parent)}>
              上一级
            </Button>
          )}
        </Space>
        <List
          size="small"
          loading={loading}
          style={{ maxHeight: 320, overflow: 'auto', border: '1px solid #f0f0f0', borderRadius: 6 }}
          dataSource={dirs}
          locale={{ emptyText: <Empty description="没有子目录" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
          renderItem={(d) => (
            <List.Item
              style={{ cursor: 'pointer', padding: '6px 12px' }}
              onClick={() => load(d)}
            >
              <Space>
                <FolderOutlined style={{ color: '#faad14' }} />
                {name(d)}
              </Space>
            </List.Item>
          )}
        />
      </Space>
    </Modal>
  )
}
