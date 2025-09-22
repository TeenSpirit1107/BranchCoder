import React, { useEffect, useRef, useState, useCallback } from 'react';
import { viewFile, getFileDownloadUrl } from '../api/agentApi';
import { toast } from '@/components/Toast';
import * as monaco from 'monaco-editor';
import { MarkdownRenderer } from './MarkdownRenderer';
import PdfViewer from './PdfViewer';
import { Eye, Code, FileText } from 'lucide-react';
import "katex/dist/katex.min.css";

// 定义文件工具参数类型
interface FileToolArgs {
  file: string;
  [key: string]: unknown;
}

// 定义ToolContent接口
interface ToolContent {
  name: string;
  function: string;
  args: FileToolArgs;
  result?: unknown;
}

interface FileToolViewProps {
  agentId: string;
  toolContent: ToolContent;
}

const FileToolView: React.FC<FileToolViewProps> = ({ agentId, toolContent }) => {
  const [fileContent, setFileContent] = useState('');
  const [viewMode, setViewMode] = useState<'preview' | 'editor'>('preview');
  const monacoContainerRef = useRef<HTMLDivElement | null>(null);
  const editorRef = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);

  // 从toolContent获取文件路径
  const filePath = toolContent?.args?.file || '';

  // 获取文件名
  const fileName = filePath ? filePath.split('/').pop() || '' : '';

  // 检查是否为markdown文件
  const isMarkdownFile = (filename: string): boolean => {
    const extension = filename.split('.').pop()?.toLowerCase() || '';
    return ['md', 'markdown'].includes(extension);
  };

  // 检查是否为PDF文件
  const isPdfFile = (filename: string): boolean => {
    const extension = filename.split('.').pop()?.toLowerCase() || '';
    return extension === 'pdf';
  };

  // 根据文件扩展名推断语言
  const getLanguage = (filename: string): string => {
    const extension = filename.split('.').pop()?.toLowerCase() || '';
    const languageMap: Record<string, string> = {
      js: 'javascript',
      ts: 'typescript',
      html: 'html',
      css: 'css',
      json: 'json',
      py: 'python',
      java: 'java',
      c: 'c',
      cpp: 'cpp',
      go: 'go',
      md: 'markdown',
      markdown: 'markdown',
      txt: 'plaintext',
      vue: 'html',
      jsx: 'javascript',
      tsx: 'typescript',
    };

    return languageMap[extension] || 'plaintext';
  };

  // 初始化Monaco编辑器
  const initMonacoEditor = useCallback(() => {
    if (monacoContainerRef.current && viewMode === 'editor') {
      // 如果编辑器已存在，直接返回
      if (editorRef.current) {
        return;
      }

      const language = getLanguage(filePath);

      editorRef.current = monaco.editor.create(monacoContainerRef.current, {
        value: fileContent,
        language,
        theme: 'vs',
        readOnly: true,
        minimap: { enabled: false },
        scrollBeyondLastLine: false,
        automaticLayout: true,
        lineNumbers: 'on',
        wordWrap: 'on',
        scrollbar: {
          vertical: 'auto',
          horizontal: 'auto',
        },
      });
    }
  }, [filePath, fileContent, viewMode]);

  // 清理Monaco编辑器
  const disposeMonacoEditor = useCallback(() => {
    if (editorRef.current) {
      editorRef.current.dispose();
      editorRef.current = null;
    }
  }, []);

  // 加载文件内容
  const loadFileContent = useCallback(() => {
    if (!filePath) return;
    
    // PDF文件不需要加载文本内容
    if (isPdfFile(fileName)) return;

    viewFile(agentId, filePath)
      .then((response) => {
        if (fileContent !== response.content) {
          setFileContent(response.content);
          if (editorRef.current) {
            // 使用编辑器模型直接更新内容，减少重新渲染开销
            const model = editorRef.current.getModel();
            if (model) {
              model.setValue(response.content);
            } else {
              editorRef.current.setValue(response.content);
            }
            const editorModel = editorRef.current.getModel();
            if (editorModel) {
              monaco.editor.setModelLanguage(editorModel, getLanguage(filePath));
            }
          }
        }
      })
      .catch((error) => {
        console.error('加载文件内容失败:', error);
        toast.error('加载文件内容失败');
      });
  }, [filePath, fileContent, agentId, fileName]);

  // 切换视图模式
  const toggleViewMode = useCallback(() => {
    const newMode = viewMode === 'preview' ? 'editor' : 'preview';
    setViewMode(newMode);
    
    if (newMode === 'editor') {
      // 切换到编辑器模式时，清理现有编辑器并重新初始化
      disposeMonacoEditor();
      // 延迟初始化，确保DOM已更新
      setTimeout(() => {
        initMonacoEditor();
      }, 0);
    } else {
      // 切换到预览模式时，清理编辑器
      disposeMonacoEditor();
    }
  }, [viewMode, disposeMonacoEditor, initMonacoEditor]);

  // 当文件路径变化时加载文件内容
  useEffect(() => {
    if (filePath) {
      loadFileContent();
    }
  }, [filePath, loadFileContent]);

  // 组件挂载时初始化
  useEffect(() => {
    // 对于PDF文件，使用PDF查看器；对于markdown文件，默认使用预览模式；其他文件使用编辑器模式
    const defaultMode = isPdfFile(fileName) ? 'preview' : (isMarkdownFile(fileName) ? 'preview' : 'editor');
    setViewMode(defaultMode);
    
    if (filePath) {
      loadFileContent();
    }
  }, [agentId, toolContent, fileName, filePath, loadFileContent]);

  // 当视图模式变化时，处理编辑器初始化
  useEffect(() => {
    // PDF文件不需要Monaco编辑器
    if (isPdfFile(fileName)) return;
    
    if (viewMode === 'editor' && fileContent) {
      // 延迟初始化，确保DOM已更新
      setTimeout(() => {
        initMonacoEditor();
      }, 0);
    }
    
    return () => {
      if (viewMode !== 'editor') {
        disposeMonacoEditor();
      }
    };
  }, [viewMode, fileContent, initMonacoEditor, disposeMonacoEditor, fileName]);

  // 组件卸载时清理编辑器
  useEffect(() => {
    return () => {
      disposeMonacoEditor();
    };
  }, [disposeMonacoEditor]);

  const isMarkdown = isMarkdownFile(fileName);
  const isPdf = isPdfFile(fileName);

  return (
    <>
      <div className="h-[36px] flex items-center px-3 w-full bg-[var(--background-gray-main)] border-b border-[var(--border-main)] rounded-t-[12px] shadow-[inset_0px_1px_0px_0px_#FFFFFF] dark:shadow-[inset_0px_1px_0px_0px_#FFFFFF30]">
        <div className="flex-1 flex items-center justify-center">
          <div className="max-w-[250px] truncate text-[var(--text-tertiary)] text-sm font-medium text-center">
            {fileName}
          </div>
        </div>
        {(isMarkdown || isPdf) && (
          <div className="flex items-center gap-1">
            {isPdf ? (
              <div className="flex items-center gap-1 text-[var(--text-tertiary)]">
                <FileText size={14} />
                <span className="text-xs">PDF</span>
              </div>
            ) : (
              <>
                <button
                  onClick={toggleViewMode}
                  className={`p-1.5 rounded transition-colors ${
                    viewMode === 'preview'
                      ? 'bg-[var(--background-primary)] text-[var(--text-primary)]'
                      : 'text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'
                  }`}
                  title="预览模式"
                >
                  <Eye size={14} />
                </button>
                <button
                  onClick={toggleViewMode}
                  className={`p-1.5 rounded transition-colors ${
                    viewMode === 'editor'
                      ? 'bg-[var(--background-primary)] text-[var(--text-primary)]'
                      : 'text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'
                  }`}
                  title="编辑器模式"
                >
                  <Code size={14} />
                </button>
              </>
            )}
          </div>
        )}
      </div>
      <div className="flex-1 min-h-0 w-full overflow-y-auto">
        <div
          dir="ltr"
          data-orientation="horizontal"
          className="flex flex-col min-h-0 h-full relative"
        >
          <div
            data-state="active"
            data-orientation="horizontal"
            role="tabpanel"
            tabIndex={0}
            className="focus-visible:outline-none data-[state=inactive]:hidden flex-1 min-h-0 h-full text-sm flex flex-col py-0 outline-none overflow-auto"
          >
            {isPdf ? (
              <PdfViewer fileUrl={getFileDownloadUrl(agentId, filePath)} />
            ) : isMarkdown && viewMode === 'preview' ? (
              <div className="flex-1 p-4 overflow-auto">
                <div className="prose prose-sm max-w-none dark:prose-invert prose-pre:bg-gray-100 dark:prose-pre:bg-gray-800 prose-code:bg-gray-100 dark:prose-code:bg-gray-800 prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-code:text-sm prose-table:border-collapse prose-th:border prose-th:border-gray-300 dark:prose-th:border-gray-600 prose-th:px-3 prose-th:py-2 prose-th:bg-gray-50 dark:prose-th:bg-gray-700 prose-td:border prose-td:border-gray-300 dark:prose-td:border-gray-600 prose-td:px-3 prose-td:py-2">
                  <MarkdownRenderer content={fileContent} />
                </div>
              </div>
            ) : (
              <section
                style={{
                  display: 'flex',
                  position: 'relative',
                  textAlign: 'initial',
                  width: '100%',
                  height: '100%',
                }}
              >
                <div ref={monacoContainerRef} style={{ width: '100%', height: '100%' }}></div>
              </section>
            )}
          </div>
        </div>
      </div>
    </>
  );
};

export default FileToolView;