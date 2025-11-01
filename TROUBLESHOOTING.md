# 故障排查指南

如果遇到 "There is no data provider registered that can provide view data" 错误，请按以下步骤排查：

## 步骤 1: 确认扩展已编译

```bash
npm run compile
```

确保没有编译错误。

## 步骤 2: 完全重新加载

1. **停止当前的调试会话**（如果正在运行）
2. **关闭所有调试窗口**
3. **重新启动调试**（按 F5）
4. **等待 VS Code 完全启动**

## 步骤 3: 检查扩展是否激活

在调试控制台（Debug Console）中查看是否有以下日志：
```
AI Chat Extension is activating...
AI Chat Extension registered view provider: aiChat.chatView
```

如果没有看到这些日志，说明扩展没有正确激活。

## 步骤 4: 检查视图是否被解析

当你点击 AI Chat 图标时，应该在调试控制台看到：
```
Resolving webview view: aiChat.chatView
```

如果没有看到，说明视图提供者没有被调用。

## 步骤 5: 手动激活视图

1. 按 `Ctrl+Shift+P` (Windows/Linux) 或 `Cmd+Shift+P` (Mac)
2. 输入 `Developer: Reload Window`
3. 等待窗口重新加载
4. 再次尝试点击 AI Chat 图标

## 步骤 6: 检查活动栏

确认左侧活动栏中是否显示了 AI Chat 图标（💬）。如果没有：
- 右键点击活动栏，选择"重置视图位置"
- 或检查活动栏设置，确保所有视图都可见

## 步骤 7: 验证 package.json 配置

确保 `package.json` 中的视图 ID 与代码中的 viewType 完全匹配：
- package.json: `"id": "aiChat.chatView"`
- extension.ts: `viewType = 'aiChat.chatView'`

## 步骤 8: 检查 Node 模块

如果仍然有问题，尝试重新安装依赖：
```bash
rm -rf node_modules
npm install
npm run compile
```

## 常见问题

### 问题：扩展激活了但视图显示错误
**解决方案**: 确保 `out/extension.js` 文件是最新的。删除 `out` 文件夹，重新编译。

### 问题：看不到活动栏图标
**解决方案**: 
- 检查 `viewsContainers` 配置是否正确
- 尝试重置 VS Code 工作区设置

### 问题：视图打开但显示空白
**解决方案**: 
- 检查 `media/chat.css` 文件是否存在
- 查看调试控制台是否有 CSS 加载错误

## 如果所有步骤都失败

请检查调试控制台的完整错误信息，并确保：
1. VS Code 版本 >= 1.74.0
2. Node.js 版本兼容
3. 所有文件都已保存
4. TypeScript 编译没有警告或错误

