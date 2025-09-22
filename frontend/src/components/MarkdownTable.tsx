import { useState, useRef, useCallback } from "react";
import { cn } from "@/utils/cn";
import { Check, Copy } from "lucide-react";
import { useTranslation } from "react-i18next";

interface MarkdownTableProps extends React.HTMLAttributes<HTMLTableElement> {}

export const MarkdownTable = (props: MarkdownTableProps) => {
  const { t } = useTranslation();
  const [isCopied, setIsCopied] = useState(false);
  const tableRef = useRef<HTMLTableElement>(null);
  
  // 处理复制表格内容
  const handleCopy = useCallback(() => {
    if (!tableRef.current) return;
    
    // 提取表格数据
    const rows = Array.from(tableRef.current.querySelectorAll('tr'));
    
    // 检查是否有表头
    const hasHeader = tableRef.current.querySelector('thead') !== null;
    
    // 将表格数据转换为结构化格式
    const tableData = rows.map(row => {
      return Array.from(row.querySelectorAll('th, td'))
        .map(cell => cell.textContent?.trim() || '')
    });
    
    // 创建用于复制的HTML表格元素
    const tempTable = document.createElement('table');
    const thead = hasHeader ? document.createElement('thead') : null;
    const tbody = document.createElement('tbody');
    
    rows.forEach((row, rowIndex) => {
      const newRow = document.createElement('tr');
      const cells = Array.from(row.querySelectorAll('th, td'));
      
      cells.forEach(cell => {
        const isHeader = cell.tagName.toLowerCase() === 'th';
        const newCell = document.createElement(isHeader ? 'th' : 'td');
        newCell.textContent = cell.textContent || '';
        newRow.appendChild(newCell);
      });
      
      if (rowIndex === 0 && hasHeader) {
        thead?.appendChild(newRow);
      } else {
        tbody.appendChild(newRow);
      }
    });
    
    if (thead) {
      tempTable.appendChild(thead);
    }
    tempTable.appendChild(tbody);
    
    // 转换为纯文本格式（用于不支持富文本的场景）
    let tableText = '';
    
    // 如果有表头，生成Markdown表格格式
    if (hasHeader && tableData.length > 1) {
      // 获取最大列宽数组
      const columnCount = Math.max(...tableData.map(row => row.length));
      const widths = Array(columnCount).fill(0);
      
      // 计算每列的最大宽度
      tableData.forEach(row => {
        row.forEach((cell, i) => {
          widths[i] = Math.max(widths[i], cell.length);
        });
      });
      
      // 生成markdown表格
      tableText = tableData.map((row, rowIndex) => {
        const formattedRow = row.map((cell, i) => cell.padEnd(widths[i], ' ')).join(' | ');
        
        // 如果是第一行后面，添加分隔符行
        if (rowIndex === 0 && hasHeader) {
          const separators = widths.map(w => '-'.repeat(w));
          return formattedRow + '\n' + separators.join(' | ');
        }
        
        return formattedRow;
      }).join('\n');
    } else {
      // 简单TSV格式
      tableText = tableData.map(row => row.join('\t')).join('\n');
    }
    
    // 使用 Clipboard API 支持富文本复制
    const htmlContent = tempTable.outerHTML;
    
    // 创建一个新的 ClipboardItem 对象
    const clipboardItem = new ClipboardItem({
      'text/plain': new Blob([tableText], { type: 'text/plain' }),
      'text/html': new Blob([htmlContent], { type: 'text/html' })
    });
    
    // 使用 clipboard.write API 复制到剪贴板
    navigator.clipboard.write([clipboardItem]).then(() => {
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    }).catch(() => {
      // 如果不支持富文本复制，回退到纯文本
      navigator.clipboard.writeText(tableText).then(() => {
        setIsCopied(true);
        setTimeout(() => setIsCopied(false), 2000);
      });
    });
  }, []);
  
  return (
    <div className="relative my-4 rounded-lg overflow-hidden shadow-sm table-group">
      <div className="overflow-x-auto">
        <table 
          ref={tableRef} 
          className={cn(
            "bg-background hover:bg-background",
            "[&_th]:bg-background hover:bg-background [&_tr]:bg-background [&_tr]:hover:bg-background [&_td]:bg-background [&_td]:hover:bg-background",
            "w-full text-sm border-collapse",
            // 左右边框去除
            "[&_th]:border-l-0 [&_th]:border-r-0 [&_td]:border-l-0 [&_td]:border-r-0 [&_tr]:border-l-0 [&_tr]:border-r-0",
            // 表头
            "[&_th]:font-semibold [&_th]:px-0 [&_th]:text-left",
            "[&_th]:border-b-1 [&_th]:border-border",
            // 表格内容
            "[&_td]:px-0 [&_td]:border-t-1 [&_td]:border-border [&_td]:font-normal",
            "[&_tr:last-child_td]:border-b-0 [&_tr]:py-3",
            // 移动设备适配
            "sm:text-sm text-xs",
            "[&_th]:pl-0 [&_th]:py-3",
            "[&_td]:pl-0 [&_td]:pr-6 [&_td]:py-3",
            props.className
          )} 
          {...props} 
        >
          {props.children}
        </table>
      </div>
      <button 
        onClick={handleCopy}
        className={cn(
          "absolute bottom-0 right-0 p-1.5 rounded-md",
          "transition-all duration-200",
          "hover:bg-accent hover:text-accent-foreground",
          "text-muted-foreground",
          "z-10",
          "flex items-center justify-center",
          "opacity-0 table-group-hover:opacity-100"
        )}
        title={isCopied ? t("MarkdownTable.copied") : t("MarkdownTable.copyTable")}
        aria-label={isCopied ? t("MarkdownTable.copied") : t("MarkdownTable.copyTable")}
        disabled={isCopied}
      >
        {isCopied ? (
          <Check className="w-4 h-4 animate-in slide-in-from-bottom-2 duration-300" />
        ) : (
          <Copy className="w-4 h-4" />
        )}
      </button>
    </div>
  );
};