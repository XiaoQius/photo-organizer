import { Layout as AntLayout, Menu } from 'antd'
import {
  DashboardOutlined,
  PictureOutlined,
  FolderOpenOutlined,
  CopyOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'

const MENU_ITEMS = [
  { key: '/', icon: <DashboardOutlined />, label: '工作台' },
  { key: '/gallery', icon: <PictureOutlined />, label: '照片墙' },
  { key: '/organize', icon: <FolderOpenOutlined />, label: '整理归档' },
  { key: '/duplicates', icon: <CopyOutlined />, label: '清理中心' },
  { key: '/settings', icon: <SettingOutlined />, label: '设置' },
]

export default function Layout() {
  const navigate = useNavigate()
  const location = useLocation()

  const selectedKey =
    MENU_ITEMS.filter((m) => m.key !== '/' && location.pathname.startsWith(m.key))
      .sort((a, b) => b.key.length - a.key.length)[0]?.key ?? '/'

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <AntLayout.Sider
        className="modern-sider"
        theme="light"
        breakpoint="lg"
        collapsedWidth="0"
        width={208}
      >
        <div className="brand" onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>
          <div className="brand-logo">◈</div>
          <div>
            <div className="brand-name">照片整理</div>
            <div className="brand-sub">本地媒体管理</div>
          </div>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          items={MENU_ITEMS}
          onClick={({ key }) => navigate(key)}
        />
      </AntLayout.Sider>
      <AntLayout>
        <AntLayout.Content style={{ padding: '24px 28px 40px', overflow: 'auto' }}>
          <div className="app-content">
            <Outlet />
          </div>
        </AntLayout.Content>
      </AntLayout>
    </AntLayout>
  )
}
