from typing import Dict, Any, List, Optional
import logging
from app.domain.services.tools.base import BaseTool, tool
from app.domain.external.llm import ReasonLLM

logger = logging.getLogger(__name__)

class DeepReasoningTool(BaseTool):
    """深度推理工具"""

    name: str = "reasoning"

    def __init__(self, reason_llm: ReasonLLM):
        """Initialize deep reasoning tool class
        
        Args:
            reason_llm: Reasoning LLM service
        """
        super().__init__()
        self.reason_llm = reason_llm

    @tool(
        name="deep_reasoning",
        description="Perform deep reasoning analysis on complex problems. Use for logical analysis, code problem solving, and critical thinking.",
        parameters={
            "problem": {
                "type": "string",
                "description": "The problem or question that requires deep reasoning"
            },
            "context": {
                "type": "string",
                "description": "Optional background information or context for the problem"
            }
        },
        required=["problem", "context"]
    )
    async def deep_reasoning(self, problem: str, context: str) -> str:
        """
        进行深度推理分析
        
        Args:
            problem: 需要推理的问题
            context: 可选的上下文信息
            
        Returns:
            推理分析结果
        """
        try:
            logger.info(f"开始深度推理: {problem[:50]}...")
            
            result = await self.reason_llm.deep_reasoning(problem, context)
            
            logger.info(f"深度推理完成，结果长度: {len(result)}")
            return result
            
        except Exception as e:
            error_msg = f"深度推理失败: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
