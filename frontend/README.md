# AI Manus React应用

这个项目是AI Manus的React前端实现，基于Vite + React + TypeScript构建。

## 功能特性

- 基于React和TypeScript构建的现代Web应用
- 使用Vite作为构建工具，实现快速开发体验
- 响应式UI设计，适配不同屏幕尺寸
- 国际化支持，包含中文和英文
- 实时聊天功能
- Tailwind CSS用于样式处理

## 安装和运行

### 前提条件

- Node.js 16+
- npm 8+

### 安装依赖

```bash
# 进入项目目录
cd frontend/react-app

# 安装依赖
npm install
```

### 开发环境运行

```bash
npm run dev
```

开发服务器将在 http://localhost:5173 启动。

### 构建生产版本

```bash
npm run build
```

构建的文件将输出到 `dist` 目录。

### 预览构建结果

```bash
npm run preview
```

## 项目结构

```
react-app/
├── public/             # 静态资源
├── src/                # 源代码
│   ├── api/            # API服务
│   ├── assets/         # 静态资源和样式
│   │   ├── locales/    # 国际化翻译文件
│   ├── components/     # 可复用组件
│   ├── constants/      # 常量定义
│   ├── pages/          # 页面组件
│   ├── types/          # TypeScript类型定义
│   ├── utils/          # 工具函数
│   ├── App.tsx         # 应用入口组件
│   └── main.tsx        # 应用主入口
├── .env.development    # 开发环境变量
├── .env.production     # 生产环境变量
├── index.html          # HTML模板
├── package.json        # 项目依赖和脚本
├── postcss.config.js   # PostCSS配置
├── tailwind.config.js  # Tailwind CSS配置
├── tsconfig.json       # TypeScript配置
└── vite.config.ts      # Vite配置
```

## 添加新组件

1. 在 `src/components` 目录中创建新组件
2. 在需要使用的地方导入组件

## 添加新页面

1. 在 `src/pages` 目录中创建新页面组件
2. 在 `App.tsx` 中为新页面添加路由 