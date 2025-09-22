// 引入 Markdown 渲染支持
import ReactMarkdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { cn } from "@/utils/cn";

// 引入样式 - 静态导入样式而不是动态导入
import "katex/dist/katex.min.css";

// 主题获取
import { CodeBlock } from "./CodeBlock";
import { useMemo, useRef, useEffect } from "react";
import { MarkdownTable } from "./MarkdownTable";

// 辅助函数：检测是否为移动设备
function isMobileDevice(): boolean {
  return (
    typeof window !== "undefined" &&
    (window.innerWidth <= 768 ||
      /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(
        navigator.userAgent
      ))
  );
}

// 组件

interface MarkdownRendererProps {
  content: string;
}

export const MarkdownRenderer = ({
  content,
}: MarkdownRendererProps) => {
  const isMobile = useRef<boolean>(false);
  
  // 在组件挂载时检测是否为移动设备
  useEffect(() => {
    isMobile.current = isMobileDevice();
    
    // 监听窗口大小变化以更新移动设备状态
    const handleResize = () => {
      isMobile.current = isMobileDevice();
    };
    
    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  const processedContent = useMemo(() => {
    // 去除```前面的空格
    let result = content;
    result = result.replace(/^\s*```/, "");
    return result;
  }, [content]);

  // 使用 useMemo 缓存 Markdown 渲染结果，仅在 content 或 theme 变化时重新计算
  const memoizedMarkdown = useMemo(() => {
    return (
      <ReactMarkdown
        children={processedContent}
        rehypePlugins={[rehypeKatex, rehypeRaw]} // 添加 rehypeRaw 插件以支持原始 HTML
        remarkPlugins={[remarkGfm, remarkMath]} // GFM 和数学公式支持
        components={{
            code({ children, className, ...rest }) {
              const match = /language-(\w+)/.exec(className || ""); // 语言匹配
              return match ? ( // 三元运算符，如果匹配到语言则使用 SyntaxHighlighter 组件，否则使用 code 标签
                <CodeBlock language={match[1]} {...rest}>
                  {String(children)}
                </CodeBlock>
              ) : (
                <code
                  {...rest}
                  className={`${className} text-foreground bg-muted mx-1 px-2 pb-0.5 rounded-sm text-center`}
                >
                  {children}
                </code>
              );
            },
            a({ children, ...rest }) {
              return <a className={cn("bg-muted text-muted-foreground",  
                "px-2 py-1 rounded-2xl text-xs font-medium",
                "inline-flex items-center justify-center",
                "transition-colors duration-200 hover:bg-accent hover:text-accent-foreground",
                "no-underline",
                rest.className)} {...rest} target="_blank">{children}</a>;
            },
            table({ ...tableProps }) {
              return <MarkdownTable {...tableProps} />;
            },
        }}
      />
    );
  }, [processedContent]); // 添加 t 到依赖数组

  return (
    <div>
      {memoizedMarkdown}
    </div>
  );
};
