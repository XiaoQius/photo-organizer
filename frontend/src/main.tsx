import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './theme.css'
import 'antd/dist/reset.css'

const theme = {
  token: {
    colorPrimary: '#4f46e5',
    colorInfo: '#4f46e5',
    colorLink: '#4f46e5',
    borderRadius: 10,
    colorBgLayout: '#f7f8fa',
    colorBgContainer: '#ffffff',
    colorBorder: '#eceef1',
    colorBorderSecondary: '#eceef1',
    colorText: '#17181c',
    colorTextSecondary: '#6f7480',
    fontFamily:
      "-apple-system, 'PingFang SC', 'HarmonyOS Sans SC', 'MiSans', 'Microsoft YaHei UI', 'Segoe UI', sans-serif",
    boxShadowSecondary: '0 12px 32px rgba(23, 24, 28, 0.12)',
  },
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN} theme={theme}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ConfigProvider>
  </React.StrictMode>,
)

