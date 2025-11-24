from ..llm.chat_llm import CompletionResult


import asyncio
from ..llm.chat_llm import AsyncChatClientWrapper

async def main():
    llm = AsyncChatClientWrapper()

    # ✅ 简单问答
    res = await llm.ask(
        messages=[{"role": "user", "content": "用一句话解释什么是超导体"}],
    )
    print("回答类型:", res["type"])
    print("回答:", res["answer"])
    print("Token 统计:", res["usage"])

    # ✅ 多协程并发调用
    tasks = [
        llm.ask(messages=[{"role": "user", "content": "讲个笑话"}]),
        llm.ask(messages=[{"role": "user", "content": "写一首关于秋天的短诗"}]),
    ]
    results = await asyncio.gather(*tasks)
    for i, r in enumerate[CompletionResult](results):
        print(f"——任务{i+1}:", r["answer"])

asyncio.run(main())
