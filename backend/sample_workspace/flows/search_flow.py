# flowchart overview
#     Start[初始化]
#     Start --> GapGen[generate_gaps 拆分gap]
#     GapGen --> Loop{gap非空且未超轮数}
#     Loop --> ParallelSearch[search_gap 并行搜索每个gap]
#     ParallelSearch --> Scoring[score_gap判分]
#     Scoring -->|满足| KnowledgeBase[存知识库]
#     Scoring -->|不满足| Analyze[analyze_gap 分析原因]
#     Analyze --> Reflect[reflect_gap 生成新gap]
#     Reflect --> UpdateGaps[更新gaps]
#     KnowledgeBase --> UpdateGaps
#     UpdateGaps --> Loop
#     Loop -- gaps空或超轮数 --> FinalQA[generate_final_answer]
#     FinalQA --> End[输出答案/终止]

# 2025/6/24 更新内容：executor不支持做并发，导致运行到search_gap整个flow断开，目前改回串行
# 必须用 format_search_result 格式化答案填入知识库，否则 summary 为空，最终 LLM 无法给出正确结论

from typing import AsyncGenerator, List, Dict, Any
from datetime import datetime
from app.domain.models.memory import Memory
from app.domain.models.plan import Plan, Step
from app.domain.models.event import AgentEvent, MessageEvent, ToolCallingEvent
from app.domain.services.flows.base import BaseSubFlow
from app.infrastructure.external.llm.openai_llm import OpenAILLM #创建gap处实现与llm对话
from app.domain.models.plan import ExecutionStatus, Plan #for executor
from app.domain.services.agents.execution import ExecutionAgent
from app.domain.models.event import (
    AgentEvent,
    StepFailedEvent,
    StepCompletedEvent,
    MessageEvent,
    ErrorEvent,
    StepStartedEvent,
    PauseEvent,
    ReportEvent
) #for executor
import asyncio
import json
from enum import Enum
from app.domain.services.prompts import search_flow_prompt as prompt
llm = OpenAILLM()

class SearchFlow(BaseSubFlow):
    flow_id = "search"
    description = "多步gap反射搜索流程"

    def __init__(
        self,
        llm,
        sandbox,
        browser,
        search_engine=None,
        audio_llm=None,
        image_llm=None,
        video_llm=None,
        reason_llm=None,
        task_type=None,
    ):
        super().__init__(
            llm=llm,
            sandbox=sandbox,
            browser=browser,
            search_engine=search_engine,
            audio_llm=audio_llm,
            image_llm=image_llm,
            video_llm=video_llm,
            reason_llm=reason_llm,
            task_type=task_type,
        )
        self.knowledge: List[Dict[str, Any]] = []
        self.max_iterations = 3

        self.processed_gaps: set = set()

        # self.executor = ExecutionAgent(
        #     memory=Memory(),
        #     llm=llm,
        #     audio_llm=audio_llm,
        #     image_llm=image_llm,
        #     video_llm=video_llm,
        #     reason_llm=reason_llm,
        #     sandbox=sandbox,
        #     browser=browser,
        #     search_engine=search_engine
        # )

        self.status = "idle"

    def is_idle(self):
        return self.status == "idle"

    async def run(
            self,
            parent_plan=None,
            parent_step=None,
            parent_memory=None,
            task_type=None,
            *args,
            **kwargs
    ) -> AsyncGenerator[AgentEvent, None]:
        """
        统一入口，兼容原有run和execute_task的参数风格。
        支持位置参数和关键字参数。
        """
        # 参数兼容处理
        memory = parent_memory or kwargs.get('memory') or Memory()
        plan = parent_plan or kwargs.get('plan')
        step = parent_step or kwargs.get('step')
        if not plan or not step:
            # 兼容通过args传参
            if len(args) >= 2:
                plan, step = args[:2]
            else:
                raise ValueError("run() 必须包含 plan 和 step 两个参数")

        self.executor = ExecutionAgent(
            memory=memory,
            llm=self.llm,
            audio_llm=self.audio_llm,
            image_llm=self.image_llm,
            video_llm=self.video_llm,
            reason_llm=self.reason_llm,
            sandbox=self.sandbox,
            browser=self.browser,
            search_engine=self.search_engine
        )


        global_question = step.description

        yield MessageEvent(message=f"初始化，目标问题：{global_question}")

        # 先选择全局评分模式列表
        eval_types = await self.select_scoring_mode(global_question)

        # gap主流程（可单独抽成私有方法，见上文）
        gaps = await self.generate_gaps(global_question)
        gaps = self._filter_and_update_gaps(gaps)
        iteration = 0

        #gaps=['下载文件Federico Lauria 2014年论文的全文']

        # 此部分while loop针对单个gap，使用reflect_gap返回针对单个gap的反思gap
        # while gaps and iteration < self.max_iterations:
        #     iteration += 1
        #     yield MessageEvent(message=f"第{iteration}轮gap处理，待处理gap: {gaps}")
        #     # search_tasks = [self.search_gap(gap) for gap in gaps]
        #     # search_results = await asyncio.gather(*search_tasks)
        #
        #     # 尝试不用并发，串行
        #     search_results = []
        #     for gap in gaps:
        #         result = await self.search_gap(gap)
        #         # print(f"[DEBUG] search_gap 返回: {result}")
        #         search_results.append(result)
        #
        #     new_gaps = []
        #
        #     for gap, result in zip(gaps, search_results):
        #         summary = self.format_search_result(result)
        #         # print("debug用， format后summary内容：")
        #         # print(summary)
        #         score, reason = await self.score_gap(gap, {"result": summary}, eval_types)
        #         if score:
        #             knowledge_item = {"gap": gap, "summary": summary, "raw": result, "iteration": iteration}
        #             self.knowledge.append(knowledge_item)
        #             yield MessageEvent(message=f"gap [{gap}] 已解决，总结: {summary}")
        #         else:
        #             error_reason = await self.analyze_gap(gap, result, reason)
        #             knowledge_item = {"gap": gap, "summary": f"失败: {error_reason}", "raw": result,
        #                               "iteration": iteration}
        #             self.knowledge.append(knowledge_item)
        #             yield MessageEvent(message=f"gap [{gap}] 未解决，错误分析: {error_reason}")
        #             reflected_gaps = await self.reflect_gap(gap, error_reason)
        #             yield MessageEvent(message=f"gap [{gap}] 反射生成新gap: {reflected_gaps}")
        #             new_gaps.extend(reflected_gaps)
        #     gaps = self._filter_and_update_gaps(gaps=[], new_gaps=new_gaps)

        # 此部分while loop针对一整轮gap，使用reflect_batch_gap返回针对一整轮gap的反思gap
        print(f"generate后gap内容为:{gaps}")
        print(type(gaps), gaps)
        while gaps and iteration < self.max_iterations:
            print("主循环开始执行")
            iteration += 1
            yield MessageEvent(message=f"第{iteration}轮gap处理，待处理gap: {gaps}")
            print(f"第{iteration}轮gap处理，待处理gap: {gaps}")

            search_results = []
            for gap in gaps:
                #result = await self.search_gap(gap)
                print("主循环中运行到executor部分")
                result = await self.search_gap(gap, global_question)
                print(f'已完成对gap： {gap} 的搜索')
                search_results.append(result)

            new_gaps = []
            failed_gaps_info = []

            for gap, result in zip(gaps, search_results):
                summary = self.format_search_result(result)
                score, reason = await self.score_gap(gap, {"result": summary}, eval_types)
                if score:
                    print(f'gap {gap} 执行成功')
                    knowledge_item = {"gap": gap, "summary": summary, "raw": result, "iteration": iteration}
                    self.knowledge.append(knowledge_item)
                    yield MessageEvent(message=f"gap [{gap}] 已解决，总结: {summary}")
                else:
                    print(f'gap {gap} 执行失败')
                    error_reason = await self.analyze_gap(gap, result, reason)
                    knowledge_item = {"gap": gap, "summary": f"失败: {error_reason}", "raw": result,
                                      "iteration": iteration}
                    self.knowledge.append(knowledge_item)
                    yield MessageEvent(message=f"gap [{gap}] 未解决，错误分析: {error_reason}")
                    failed_gaps_info.append({
                        "gap": gap,
                        "error_reason": error_reason,
                        "executor_result": result
                    })

            # 一轮gap全处理完后，统一reflect
            if failed_gaps_info:
                reflected_gaps = await self.reflect_gap_batch(failed_gaps_info)
                yield MessageEvent(message=f"本轮所有失败gap反射生成新gap: {reflected_gaps}")
                new_gaps.extend(reflected_gaps)

            gaps = self._filter_and_update_gaps(gaps=[], new_gaps=new_gaps)

        yield MessageEvent(message="gap处理完成，准备整合知识库生成最终答案")
        final_answer, need_more = await self.generate_final_answer(global_question, self.knowledge)
        parent_step.result = final_answer
        yield ReportEvent(message=f"最终答案：{final_answer}")
        print("run中已yield最终答案")
        if need_more:
            yield MessageEvent(message="LLM认为知识库仍有缺失，重新进入gap循环（本流程暂不再循环）")
        else:
            yield MessageEvent(message="任务完成，已获得满意答案")

    # ========== 以下为各模块实现 ==========

    async def select_scoring_mode(self, global_question: str)  -> List[str]:
        """
        根据 global_question 的内容简单决策评分模式。
        """

        messages = [
            {
                "role": "system",
                "content": prompt.QUESTION_EVALUATION_PROMPT_SYSTEM
            },
            {
                "role": "user",
                "content": prompt.QUESTION_EVALUATION_PROMPT_USER.format(
                    question=global_question
                ),
            },
        ]
        # 调用 LLM
        #print(f'select scoring mode的message{messages}')
        response = await self.llm.ask(messages)
        # 打印调试内容（可选）
        #print("LLM returned:", response.content)


        eval_types = []
        # 解析 LLM 输出
        try:
            analysis_result = json.loads(response.content)
        except Exception as e:
            print("LLM输出解析失败，fallback使用basic", e)
            eval_types.append("basic") #使用basic进行兜底

        if analysis_result.get("needsDefinitive", True):
            eval_types.append("definitive")
        if analysis_result.get("needsFreshness", False):
            eval_types.append("freshness")
        if analysis_result.get("needsPlurality", False):
            eval_types.append("plurality")
        if analysis_result.get("needsCompleteness", False):
            #eval_types.append("completeness")
            print()
        if analysis_result.get("needsFile", True):
            eval_types.append("file")

        print(f"[Eval] 问题需要的评估类型: {eval_types}")
        return eval_types

    #生成gap
    async def generate_gaps(self, global_question: str) -> list[str]:
        #print("generate_gaps 生成问题 运行到了")

        current_time = datetime.now()
        system_prompt = prompt.QUERY_REWRITE_PROMPT_SYSTEM.format(
            currentTime=current_time.isoformat(),
            currentYear=current_time.year,
            currentMonth=current_time.month
        )
        user_message = prompt.QUERY_GENERATE_PROMPT_USER.format(
            global_question=global_question,
            current_time=datetime.now()
        )
        messages = [
            {"role": "user", "content": system_prompt + "\n\n" + user_message},
        ]
        response = await self.llm.ask(messages)
        print("成功获取llm返回的新gaps，raw")
        print(response.content)
        try:
            data = json.loads(response.content)
            queries = data.get("queries", [])
            gaps = []
            for query in queries:
                print("开始将返回内容格式化为query")
                if isinstance(query, dict):
                    # 按字段顺序拼成 "key1:value1 key2:value2 ..."
                    fields = [f"{k}:{str(v)}" for k, v in query.items() if str(v).strip()]
                    if fields:
                        gaps.append(" ".join(fields))
                        print("gaps已经成功append")
                        print(fields)
            return gaps
        except Exception as e:
            print("解析失败:", e)
            return [global_question]

    #由run方法中串行调用，利用executor搜索单个gap
    # async def search_gap(self, gap: str) -> dict:
    #     #print("search_gap 搜索问题 运行到了")
    #     # 1. 构造一个step
    #     # step = Step(
    #     #     id="search_gap",
    #     #     description=f"请使用搜索工具检索以下内容：{gap}",
    #     #     status=ExecutionStatus.PENDING
    #     # )
    #     step = Step(
    #         id="search_gap",
    #         description=(
    #             f"You have access to all available tools, including search engines, web browsers, code execution, and multimedia analysis."
    #             f"\nPlease select the most appropriate tool(s) to solve the following sub-question. "
    #             f"Actively call the needed tools, integrate their output, and provide a clear answer."
    #             f"If you encounter a question that needs reading files(pdf/word/txt) to obtain the answer, you should try to download the file from the internet for more accurate answers."
    #             f"If you are required to find answers from related essays, articles or books, you should download them and check the file by reading them locally."
    #             f"In most conditions, searching information about content of an article/book/essay is not a good idea, not much information can be found online, download and read the file if needed."
    #             f"\nSub-question: {gap}"
    #         ),
    #         status=ExecutionStatus.PENDING
    #     )
    #
    #     # 2. 构造一个最小Plan
    #     plan = Plan(
    #         id="search_gap_plan",
    #         title="Search Gap Task",
    #         goal=gap,
    #         steps=[step]
    #     )
    #     all_messages = []
    #     final_result = None
    #     final_error = None
    #
    #     # 3. 调用executor执行，因后端executor较为标准，暂时使用，后期会针对此处使用的特定工具进行优化
    #     async for event in self.executor.execute_step(plan, step, gap):
    #         if hasattr(event, "message"):
    #             all_messages.append(event.message)
    #         if isinstance(event, StepCompletedEvent):
    #             # 把最终 result 也放到 messages 最后
    #             all_messages.append(event.step.result)
    #             return {"gap": gap, "result": all_messages}
    #         elif isinstance(event, StepFailedEvent):
    #             # 错误处理
    #             all_messages.append(event.step.error)
    #             return {"gap": gap, "result": all_messages}
    #
    #
    #     # 4. fallback，兜底
    #     #print("如果gap no result found，以下会被打印：")
    #     #print(f"[DEBUG][search_gap] gap: {gap} No result found.") #test
    #     # return {"gap": gap, "error": "No result"}
    #     all_messages.append("No result")
    #     return {"gap": gap, "result": all_messages}

    async def search_gap(self, gap: str, global_question: str = None) -> dict:
        print("search_gap被调用")
        # 1. 知识库标准化并装入prompt
        knowledge_text = ""
        if self.knowledge:
            knowledge_text = "\n".join(
                f"Sub-question: {item.get('gap', '')}\nContent: {item.get('summary', '')}"
                for item in self.knowledge
            )

        #局域prompt存储
        prompt_parts = []

        # =知识库相关prompt
        if knowledge_text:
            prompt_parts.append(
                "---- KNOWLEDGE BASE ----\n"
                "Below is the current knowledge base collected from previous sub-questions. "
                "You MUST use this information to answer the current sub-question if possible. "
                "If the knowledge base already contains a clear answer, you should directly summarize or reuse it. "
                "Only use external tools/search if the knowledge base is insufficient.\n"
                f"{knowledge_text}\n"
            )
        else:
            prompt_parts.append(
                "---- KNOWLEDGE BASE ----\n"
                "The knowledge base is currently empty. You may need to use available tools to answer the sub-question.\n"
            )
        #print(f'知识库部分：{prompt_parts}')

        #关于search_flow所需的特别的executor的prompt
        execution_prompt=prompt.EXECUTION_DESCRIPTION_PROMPT.format(
            gap=gap
        )
        prompt_parts.append(execution_prompt)

        #来自execution.py，专门用来向executor解释他的能力
        current_time = datetime.now()  # 当前本地时间，类型为datetime对象
        system_prompt = prompt.EXECUTION_SYSTEM_PROMPT.format(
            cur_time=current_time.isoformat()
        )
        prompt_parts.append(system_prompt)

        full_prompt = "\n".join(prompt_parts)

        # 3. Compose Step with new prompt
        step = Step(
            id="search_gap",
            description=full_prompt,
            status=ExecutionStatus.PENDING
        )

        #2构造一个最小Plan
        plan = Plan(
            id="search_gap_plan",
            title="Search Gap Task",
            goal=gap,
            steps=[step]
        )
        all_messages = []
        final_result = None
        final_error = None

        # 3. 调用executor执行，因后端executor较为标准，暂时使用，后期会针对此处使用的特定工具进行优化
        print("prompt制作完成，开始调用executor")
        async for event in self.executor.execute_step(plan, step, gap):
            if hasattr(event, "message"):
                all_messages.append(event.message)
                print("获取到了message")
            if isinstance(event, StepCompletedEvent):
                # 把最终 result 也放到 messages 最后
                all_messages.append(event.step.result)
                print("获取到了StepCompletedEvent")
                return {"gap": gap, "result": all_messages}
            elif isinstance(event, StepFailedEvent):
                # 错误处理
                all_messages.append(event.step.error)
                print("获取到了StepFailedEvent")
                return {"gap": gap, "result": all_messages}

        # 4. fallback，兜底
        print("如果gap no result found，以下会被打印：")
        # print(f"[DEBUG][search_gap] gap: {gap} No result found.") #test
        # return {"gap": gap, "error": "No result"}
        all_messages.append("No result")
        return {"gap": gap, "result": all_messages}


    #为gap执行结果打分，打分为boolean值
    async def score_gap(self, gap: str, result: dict, eval_types: list = None) -> (bool, str):

        #print("score_gap 评价结果 运行到了")
        """
        判断搜索结果是否满足gap问题，返回(bool, summary)
        """

        #这里改为根据eval_types选择prompt
        #遍历eval_types，检查是否每个eval_type都通过
        satisfied=True
        reason=""
        for eval_type in eval_types:
            eval_type=eval_type
            question=gap
            answer_action=result.get('result', '')[:1000]
            relevant_knowledge=["none"]
            system_prompt, user_prompt = self._get_prompts(
                eval_type, question, answer_action, relevant_knowledge
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            #print(f'为gap评分时的message{messages}')
            response = await self.llm.ask(messages)
            #print(response.content)
            # print("score_gap debug内容")
            # print(response) #test
            try:
                data = json.loads(response.content)
                passed = data.get("pass", False)
                if not passed:
                    satisfied=False
                reason = reason+data.get("think", "")
            except Exception as e:
                # 解析失败时降级为“不满足”，并输出原始内容
                satisfied=False
                reason=reason+f"LLM判分输出无法解析，原始内容：{getattr(response, 'content', '')}"
        #print(f'satisfied: {satisfied}, reason: {reason}, gap{gap}')
        return satisfied, reason


    def _get_prompts(
        self,
        eval_type: str,
        question: str,
        answer_action: str,
        knowledge: List[str],
    ) -> tuple[str, str]:
        """获取评估类型的提示词模板"""
        if eval_type == "strict":
            system_prompt = prompt.REJECT_ALL_ANSWERS_PROMPT_SYSTEM.format(
                knowledge_str="\n".join(knowledge)
            )
            user_prompt = prompt.REJECT_ALL_ANSWERS_PROMPT_USER.format(
                question=question, answer=answer_action
            )
        elif eval_type == "definitive":
            system_prompt = prompt.DEFEINITE_PROMPT_SYSTEM
            user_prompt = prompt.DEFEINITE_PROMPT_USER.format(
                question=question, answer=answer_action
            )
        elif eval_type == "freshness":
            system_prompt = prompt.FRESHNESS_PROMPT_SYSTEM.format(
                currentTime=datetime.now().isoformat()
            )
            user_prompt = prompt.FRESHNESS_PROMPT_USER.format(
                question=question, answer=answer_action
            )
        elif eval_type == "completeness":
            system_prompt = prompt.COMPLETENESS_PROMPT_SYSTEM
            user_prompt = prompt.COMPLETENESS_PROMPT_USER.format(
                question=question, answer=answer_action
            )
        elif eval_type == "plurality":
            system_prompt = prompt.PLURALITY_PROMPT_SYSTEM
            user_prompt = prompt.PLURALITY_PROMPT_USER.format(
                question=question, answer=answer_action
            )
        elif eval_type == "basic":
            system_prompt = prompt.BASIC_PROMPT_SYSTEM
            user_prompt = prompt.BASIC_PROMPT_USER.format(
                question=question, answer=answer_action
            )
        elif eval_type == "file":
            system_prompt = prompt.FILE_PROMPT_SYSTEM
            user_prompt = prompt.FILE_PROMPT_USER.format(
                question=question, answer=answer_action
            )
        else:
            raise ValueError(f"未知的评估类型: {eval_type}")

        return system_prompt, user_prompt


    #analyze分析本次gap执行错误的原因
    async def analyze_gap(self, gap: str, result: dict, reason:str) -> str:
        #print("analyze_gap 分析失败原因 运行到了")
        """
        分析gap未被解决的原因，返回分析文本
        """
        prompt = f"""
    你是一个问题诊断专家。现在有一个子问题未能通过已有搜索内容得到解答，请分析原因，并用一句话简明扼要地说明。不要输出多余内容。

    子问题：{gap}
    搜索内容：{result.get('result', '')[:1000]}
    对该子问题未成功解决的简单分析{reason}
    未解决原因：
    """
        messages = [
            {"role": "user", "content": prompt}
        ]
        #print(f'分析问题失败原因的message{messages}')
        response = await self.llm.ask(messages)
        # 直接返回 LLM 输出内容
        return getattr(response, "content", "").strip()

    #reflect负责根据失败原因提供新的gap
    async def reflect_gap(self, gap: str, error_reason: str) -> list[str]:
        """
        用LLM结合gap和失败原因，生成新的gap（子问题）或改进的检索表达。
        """
        #print("运行到反射错误问题！！！！！！！！！！！！！！！！！！！！！！！！！！！！")

        current_time = datetime.now()  # 当前本地时间，类型为datetime对象
        current_year = current_time.year  # 当前年份，整数
        current_month = current_time.month

        system_prompt = prompt.QUERY_REWRITE_PROMPT_SYSTEM.format(
            currentTime=current_time.isoformat(),
            currentYear=current_year,
            currentMonth=current_month
        )
        user_message = prompt.QUERY_REWRITE_PROMPT_USER.format(
            query=gap,
            think="分析用户搜索意图，生成更精确的查询",
            context=error_reason
        )
        messages = [
            {"role": "user", "content": system_prompt + "\n\n" + user_message},
        ]
        #print(f'反射新gap的message{messages}')
        response = await self.llm.ask(messages)
        print("成功获取llm返回的新gaps，raw")
        print(response.content)
        try:
            data = json.loads(response.content)
            queries = data.get("queries", [])
            gaps = []
            for query in queries:
                print("开始将返回内容格式化为query")
                if isinstance(query, dict):
                    # 按字段顺序拼成 "key1:value1 key2:value2 ..."
                    fields = [f"{k}:{str(v)}" for k, v in query.items() if str(v).strip()]
                    if fields:
                        gaps.append(" ".join(fields))
                        print("gaps已经成功append")
                        print(fields)
            return gaps
        except Exception as e:
            print("解析失败:", e)
            return []

    #reflect batch负责一整轮gap结束后的反思以及提供新gap，实现一个简单的没有plan的递进
    async def reflect_gap_batch(self, failed_gaps_info: list[dict]) -> list[str]:
        """
        批量反射：输入多组gap及分析，生成新gap列表
        """
        current_time = datetime.now()
        prompt_lines = []
        for i, info in enumerate(failed_gaps_info, 1):
            prompt_lines.append(
                f"{i}. 子问题: {info['gap']}\n失败原因: {info['error_reason']}\n执行器内容: {self.format_search_result(info['executor_result'])}\n"
            )
        prompt_str = "\n".join(prompt_lines) #本轮子问题以及失败原因，用于生成新gap
        system_prompt = prompt.QUERY_REWRITE_PROMPT_SYSTEM.format(
            currentTime=current_time.isoformat(),
            currentYear=current_time.year,
            currentMonth=current_time.month
        )
        user_message = prompt.QUERY_REWRITE_PROMPT_USER.format(
            query_group=prompt_str,
        )
        #user_message = f"以下是本轮未解决的子问题、失败原因和相关内容，请针对每个子问题，结合失败原因给出更精确、可直接搜索的新子问题表达，输出如下格式JSON：\n{{\n  \"queries\": [\"新子问题1\", \"新子问题2\", ...]\n}}\n\n{prompt_str}"
        messages = [
            {"role": "user", "content": system_prompt + "\n\n" + user_message},
        ]
        response = await self.llm.ask(messages)
        try:
            data = json.loads(response.content)
            return [str(q).strip() for q in data.get("queries", []) if q]
        except Exception as e:
            print("批量reflect解析失败:", e)
            return []


    #为避免出现过于相似或者重复的gap，generate后使用filter去重
    def _filter_and_update_gaps(self, gaps, new_gaps=None):
        #print("过滤更新 运行到了")
        """
        对gaps去重，并更新已处理过的gaps集合。
        如果提供了new_gaps，则只处理new_gaps，否则处理gaps。
        返回未被处理过的新gap列表。
        """
        target_gaps = new_gaps if new_gaps is not None else gaps
        filtered = [g for g in target_gaps if g not in self.processed_gaps]
        self.processed_gaps.update(filtered)
        return filtered

    #此处规范化result，保证知识库内信息不为空
    def format_search_result(self, result: dict) -> str:
        #print("格式化结果 运行到了")
        """
        泛用型，将搜索结果dict转为可读文本。
        1. 如果是字符串，直接返回；
        2. 如果是列表，则递归格式化每项，合并输出；
        3. 如果是dict，尝试读取常见字段，如title、content、summary等，并递归格式化；
        4. 如果有error，则优先返回error文本；
        5. 其它类型，直接转字符串。
        """
        if not result:
            return "（无搜索结果）"
        if isinstance(result, str):
            return result.strip()
        if isinstance(result, list):
            # 多条结果，递归格式化每条
            return "\n".join(self.format_search_result(item) for item in result)
        if isinstance(result, dict):
            if "error" in result and result["error"]:
                return f"查询失败：{result['error']}"
            # 优先展示result字段
            if "result" in result:
                # result字段本身可能是字符串、dict或list
                return self.format_search_result(result["result"])
            # 常见内容字段
            text_pieces = []
            for key in ("title", "question", "summary", "content", "description", "answer"):
                if key in result and result[key]:
                    text_pieces.append(str(result[key]).strip())
            # 其它字段也拼一下
            other_keys = [k for k in result if
                          k not in ("title", "question", "summary", "content", "description", "answer", "error",
                                    "result") and result[k]]
            for k in other_keys:
                text_pieces.append(f"{k}: {result[k]}")
            if text_pieces:
                return "\n".join(text_pieces)
            # 如果没有可用字段，直接输出dict
            return str(result)
        # 其它类型
        return str(result)

    #最后一步，生成最终报告
    async def generate_final_answer(self, global_question: str, knowledge: list[dict]) -> (str, bool):
        print("生成最终答案 运行到了")
        """
        用LLM综合知识库和global question生成最终答案，并判断是否还需补充信息。
        返回：(最终答案, 需补充True/False)
        """
        # 将知识库内容整理成可阅读的字符串
        knowledge_text = "\n\n".join(
            f"【子问题】：{item.get('gap', '')}\n【内容】：{item.get('summary', '')}" for item in knowledge
        )

        prompt = f"""
    你现在是一位专业问答助手。请根据下方已收集的知识点，回答全局问题。
    如果你认为已有知识完全可以支持准确回答，请给出最终答案，并标记"need_more"为false；如果你认为知识还不够，无法回答或有重大遗漏，请标记"need_more"为true，并简要说明原因。
    只允许输出如下JSON格式（不要有任何其他内容）：

    {{
      "answer": "最终答案内容",
      "need_more": true/false,
      "reason": "如需补充知识，说明原因，否则可省略"
    }}

    全局问题：{global_question}

    知识库内容：
    {knowledge_text}
    """
        messages = [
            {"role": "user", "content": prompt}
        ]
        #print(f'最终答案生成message{messages}')
        response = await self.llm.ask(messages)
        try:
            data = json.loads(response.content)
            answer = data.get("answer", "").strip()
            need_more = bool(data.get("need_more", False))
            print("最终答案生成成功")
            return answer, need_more
        except Exception:
            # 解析失败时降级为“无法回答，需补充”
            return "（无法解析LLM的回答，请补充知识）", True

    # ========== 可选 summary/report 接口 ==========
    # 两个方法视情况使用，目前在代码中并未用到

    async def summarize_execution(self) -> AsyncGenerator[AgentEvent, None]:
        yield MessageEvent(message="搜索流程执行总结")
        # 可以输出 self.knowledge 等

    async def generate_report(self) -> AsyncGenerator[AgentEvent, None]:
        yield MessageEvent(message="搜索流程最终报告")
        # 可以输出 self.knowledge 等