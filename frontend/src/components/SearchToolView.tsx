import React from 'react';

// 定义ToolContent接口
interface ToolContent {
  name: string;
  function: string;
  args: any;
  result?: any;
}

interface SearchToolViewProps {
  agentId: string;
  toolContent: ToolContent;
}

interface SearchResult {
  title: string;
  link: string;
  snippet: string;
}

const SearchToolView: React.FC<SearchToolViewProps> = ({ toolContent }) => {
  // 从toolContent获取搜索结果
  const searchResults: SearchResult[] = toolContent.result?.data?.results || [];

  return (
    <>
      <div className="h-[36px] flex items-center px-3 w-full bg-[var(--background-gray-main)] border-b border-[var(--border-main)] rounded-t-[12px] shadow-[inset_0px_1px_0px_0px_#FFFFFF] dark:shadow-[inset_0px_1px_0px_0px_#FFFFFF30]">
        <div className="flex-1 flex items-center justify-center">
          <div className="max-w-[250px] truncate text-[var(--text-tertiary)] text-sm font-medium text-center">
            Search
          </div>
        </div>
      </div>
      <div className="flex-1 min-h-0 w-full overflow-y-auto">
        <div className="flex-1 min-h-0 max-w-[640] mx-auto">
          <div className="flex flex-col overflow-auto h-full px-4 py-3">
            {searchResults.map((result, index) => (
              <div key={index} className="py-3 pt-0 border-b border-[var(--border-light)]">
                <a
                  href={result.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block text-[var(--text-primary)] text-sm font-medium hover:underline line-clamp-2 cursor-pointer"
                >
                  {result.title}
                </a>
                <div className="text-[var(--text-tertiary)] text-xs mt-0.5 line-clamp-3">
                  {result.snippet}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
};

export default SearchToolView; 