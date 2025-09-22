import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useState, useCallback } from "react";
import { Copy, Check } from "lucide-react";

interface CodeBlockProps {
  children: string;
  language: string;
  [key: string]: unknown; // 支持传递其他属性
}

export const CodeBlock = ({
  children,
  language,
  ...rest
}: CodeBlockProps) => {
  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard
      .writeText(String(children).replace(/\n$/, ""))
      .then(() => {
        setIsCopied(true);
        setTimeout(() => setIsCopied(false), 1500); // 1.5秒后重置复制状态
      })
      .catch((err) => {
        console.error("Failed to copy text: ", err);
      });
  }, [children]);

  return (
    <div className="relative">
      <div className="flex items-center text-muted-foreground px-4 py-2 text-xs justify-between h-9 bg-muted select-none rounded-t-[5px]">
        {language}
      </div>
      <div className="sticky top-8 z-10">
        <div className="flex items-center rounded bg-muted absolute bottom-1.5 right-3">
          <button
            onClick={handleCopy}
            className="flex gap-1 items-center select-none px-3 py-1 text-xs text-muted-foreground hover:bg-accent hover:text-accent-foreground rounded font-sans"
          >
            {isCopied ? (
              <Check className="h-3.5 w-3.5" />
            ) : (
              <Copy className="h-3.5 w-3.5" />
            )}
            {isCopied ? "已复制" : "复制"}
          </button>
        </div>
      </div>
      <SyntaxHighlighter
        {...rest}
        PreTag="div"
        language={language}
        style={oneLight}
        customStyle={{
          padding: "1.5rem 1rem 1rem 1rem",
          marginTop: "0",
          borderRadius: "0 0 5px 5px",
        }}
      >
        {String(children).replace(/\n$/, "")}
      </SyntaxHighlighter>
    </div>
  );
};
