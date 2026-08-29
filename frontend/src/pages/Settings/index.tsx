import { useEffect, useState } from 'react'
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Descriptions,
  Form,
  Input,
  List,
  Modal,
  Popconfirm,
  Radio,
  Select,
  Space,
  Spin,
  Typography,
  message,
} from 'antd'
import PageHeader from '../../components/PageHeader'
import { aiApi, dbApi, settingsApi, watchApi } from '../../services/api'
import type { AiConfig, DbBackup, WatchStatus } from '../../types'

const FOLDER_PRESET_MAP: Record<string, string> = {
  'Y/M': '{year}/{month}',
  'Y/M/D': '{year}/{month}/{day}',
  'Y/M/CITY': '{year}/{month}/{city}',
  'Y/CITY': '{year}/{city}',
  'Y/TYPE/M': '{type}/{year}/{month}',
}

export default function Settings() {
  const [form] = Form.useForm()
  const [saving, setSaving] = useState(false)
  const [ai, setAi] = useState<AiConfig | null>(null)
  const [watch, setWatch] = useState<WatchStatus | null>(null)
  const [watchDir, setWatchDir] = useState('')
  const [watchTarget, setWatchTarget] = useState('')
  const [autoOrganize, setAutoOrganize] = useState(false)
  const [watchWorking, setWatchWorking] = useState(false)
  const [backups, setBackups] = useState<DbBackup[]>([])
  const [dbWorking, setDbWorking] = useState(false)

  const loadBackups = () => {
    dbApi.backups().then((r) => setBackups(r.items)).catch(() => {})
  }

  const loadWatch = () => {
    watchApi.status().then((w) => {
      setWatch(w)
      setWatchDir(w.watch_dir)
      setWatchTarget(w.watch_target_dir)
      setAutoOrganize(w.watch_auto_organize)
    }).catch(() => {})
  }

  useEffect(() => {
    settingsApi.get().then((s) => form.setFieldsValue(s)).catch(() => {})
    aiApi.config().then(setAi).catch(() => {})
    loadWatch()
    loadBackups()
  }, [])

  const save = async () => {
    setSaving(true)
    try {
      const values = await form.validateFields()
      await settingsApi.update(values)
      message.success('设置已保存')
    } catch (e: any) {
      if (e?.errorFields) return
      message.error(e.response?.data?.detail || '保存失败')
    } finally {
      setSaving(false)
    }
  }

  const toggleWatch = async (enabled: boolean) => {
    setWatchWorking(true)
    try {
      await watchApi.toggle({
        enabled,
        watch_dir: watchDir,
        target_dir: watchTarget,
        auto_organize: autoOrganize,
      })
      message.success(enabled ? '监控已开启' : '监控已关闭')
      loadWatch()
    } catch (e: any) {
      message.error(e.response?.data?.detail || '操作失败')
    } finally {
      setWatchWorking(false)
    }
  }

  return (
    <Space direction="vertical" size="large" style={{ width: '100%', maxWidth: 760 }}>
      <PageHeader title="设置" subtitle="归档规则、文件夹监控与数据安全" />
      <Form form={form} layout="vertical" initialValues={{ default_mode: 'move' }}>
      <Card title="整理偏好">
          <Form.Item name="folder_structure" label="目录结构预设">
            <Select
              options={[
                { label: '年/月', value: 'Y/M' },
                { label: '年/月/日', value: 'Y/M/D' },
              ]}
              style={{ width: 240 }}
            />
          </Form.Item>
          <Form.Item name="naming" label="文件重命名预设">
            <Radio.Group>
              <Radio value="standard">统一格式（IMG_20260829_143012.jpg）</Radio>
              <Radio value="keep">保留原文件名</Radio>
            </Radio.Group>
          </Form.Item>
          <Form.Item
            name="folder_template"
            label="自定义目录模板（优先于预设）"
            extra="可用变量：{year} {month} {day} {city} {category} {type}，如 {year}/{month}/{city}"
          >
            <Input placeholder="{year}/{month}" style={{ width: 360 }} />
          </Form.Item>
          <Form.Item
            name="name_template"
            label="自定义文件名模板（优先于预设）"
            extra="可用变量：{prefix} {datetime} {original}，如 {prefix}_{datetime}"
          >
            <Input placeholder="{prefix}_{datetime}" style={{ width: 360 }} />
          </Form.Item>
          <Form.Item name="default_mode" label="默认处理方式">
            <Radio.Group>
              <Radio value="move">移动文件</Radio>
              <Radio value="copy">复制文件</Radio>
            </Radio.Group>
          </Form.Item>
      </Card>

      <Card title="扫描排除规则">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Typography.Text type="secondary">
            应用图标、依赖包、源码素材这类文件不用进媒体库？在这里排除。保存后对相关目录重新扫描，被排除的文件会转为「失效记录」，再到工作台点「清理失效记录」即可移出。
          </Typography.Text>
          <Form.Item
            name="exclude_names"
            label="忽略的目录名（逗号分隔，任意层级生效）"
            extra="默认已含 node_modules、.git、dist、build 等常见依赖/构建目录；可自行追加，如 icons,assets"
          >
            <Input.TextArea rows={2} placeholder="node_modules,.git,dist,build" />
          </Form.Item>
          <Form.Item
            name="exclude_paths"
            label="忽略的路径（每行一个绝对路径，整棵目录树跳过）"
            extra="例如软件目录、代码工作区：E:\CODEX\ZCODE"
          >
            <Input.TextArea rows={3} placeholder={'E:\\CODEX\\ZCODE'} />
          </Form.Item>
          <Button type="primary" loading={saving} onClick={save}>保存全部设置</Button>
        </Space>
      </Card>

      <Card title="文件夹监控">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Typography.Text type="secondary">
            开启后每分钟检查监控目录，发现新照片/视频自动入库；打开「自动归档」后会按当前整理规则自动移动到目标目录（相同文件自动跳过）。
          </Typography.Text>
          <Input
            placeholder="监控目录，如 D:\\相册\\微信导入"
            value={watchDir}
            onChange={(e) => setWatchDir(e.target.value)}
          />
          <Input
            placeholder="自动归档目标目录（可选）"
            value={watchTarget}
            onChange={(e) => setWatchTarget(e.target.value)}
          />
          <Checkbox
            checked={autoOrganize}
            onChange={(e) => setAutoOrganize(e.target.checked)}
          >
            自动归档新文件（按「整理偏好」中的目录/命名规则移动）
          </Checkbox>
          <Space>
            {watch?.enabled ? (
              <Button danger loading={watchWorking} onClick={() => toggleWatch(false)}>关闭监控</Button>
            ) : (
              <Button type="primary" loading={watchWorking} onClick={() => toggleWatch(true)}>开启监控</Button>
            )}
            <Button
              loading={watchWorking}
              onClick={async () => {
                setWatchWorking(true)
                try {
                  const r = await watchApi.runNow()
                  message.success(r.message)
                  loadWatch()
                } catch (e: any) {
                  message.error(e.response?.data?.detail || '检查失败')
                } finally {
                  setWatchWorking(false)
                }
              }}
            >
              立即检查一次
            </Button>
            {watch?.enabled && (
              <Typography.Text type={watch.running ? 'secondary' : 'warning'}>
                {watch.running ? `运行中 · 上次检查：${watch.last_run ?? '尚未运行'}` : '未运行'}
                {watch.last_result ? ` · ${watch.last_result}` : ''}
                {watch.error ? ` · 出错：${watch.error}` : ''}
              </Typography.Text>
            )}
          </Space>
        </Space>
      </Card>

      <Card title="数据库备份与恢复">
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <Typography.Text type="secondary">
            备份保存到后端 backups 目录（照片视频文件本身不在数据库中，不受影响）。恢复时会先把当前数据库自动备份一份，恢复后立即生效。
          </Typography.Text>
          <Space>
            <Button
              type="primary"
              loading={dbWorking}
              onClick={async () => {
                setDbWorking(true)
                try {
                  const r = await dbApi.create()
                  message.success(`已创建备份：${r.filename}`)
                  loadBackups()
                } catch (e: any) {
                  message.error(e.response?.data?.detail || '备份失败')
                } finally {
                  setDbWorking(false)
                }
              }}
            >
              创建备份
            </Button>
          </Space>
          {backups.length === 0 ? (
            <Typography.Text type="secondary">还没有备份。</Typography.Text>
          ) : (
            <List
              size="small"
              bordered
              dataSource={backups}
              renderItem={(b) => (
                <List.Item
                  actions={[
                    <Popconfirm
                      key="restore"
                      title="恢复此备份？"
                      description="当前数据库会先自动备份一份。"
                      onConfirm={async () => {
                        setDbWorking(true)
                        try {
                          const r = await dbApi.restore(b.filename)
                          message.success(`已恢复 ${r.restored}（原库已存为 ${r.safety_backup}）`)
                          loadBackups()
                        } catch (e: any) {
                          message.error(e.response?.data?.detail || '恢复失败')
                        } finally {
                          setDbWorking(false)
                        }
                      }}
                    >
                      <Button size="small" type="link">恢复</Button>
                    </Popconfirm>,
                    <Popconfirm
                      key="delete"
                      title="删除此备份文件？"
                      onConfirm={async () => {
                        try {
                          await dbApi.remove(b.filename)
                          loadBackups()
                        } catch (e: any) {
                          message.error(e.response?.data?.detail || '删除失败')
                        }
                      }}
                    >
                      <Button size="small" type="link" danger>删除</Button>
                    </Popconfirm>,
                  ]}
                >
                  <List.Item.Meta
                    title={b.filename}
                    description={`${b.created_at} · ${(b.size / 1024).toFixed(0)} KB`}
                  />
                </List.Item>
              )}
            />
          )}
        </Space>
      </Card>

      <Card title="AI 场景打标">
        {ai?.configured ? (
          <Descriptions column={1} size="small">
            <Descriptions.Item label="状态">
              <Typography.Text type="success">已配置</Typography.Text>
            </Descriptions.Item>
            <Descriptions.Item label="模型">{ai.model}</Descriptions.Item>
            <Descriptions.Item label="说明">
              在「照片墙」点击「AI 打标」可为最近 200 张照片生成场景标签（走 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 环境变量）
            </Descriptions.Item>
          </Descriptions>
        ) : (
          <Alert
            type="info"
            showIcon
            message="未配置 LLM API"
            description="设置环境变量 LLM_API_KEY、LLM_BASE_URL、LLM_MODEL 后重启服务即可启用照片场景自动打标。"
          />
        )}
      </Card>
      </Form>
    </Space>
  )
}
