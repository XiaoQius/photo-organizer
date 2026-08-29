import { Typography } from 'antd'

interface Props {
  title: string
  subtitle?: string
  extra?: React.ReactNode
}

/** 统一的页面标题区：标题 + 一句说明 + 右侧操作 */
export default function PageHeader({ title, subtitle, extra }: Props) {
  return (
    <div className="page-header" style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
      <div>
        <Typography.Title level={2} style={{ margin: 0 }}>{title}</Typography.Title>
        {subtitle && (
          <Typography.Paragraph type="secondary" style={{ margin: '4px 0 0', fontSize: 13 }}>
            {subtitle}
          </Typography.Paragraph>
        )}
      </div>
      {extra}
    </div>
  )
}
