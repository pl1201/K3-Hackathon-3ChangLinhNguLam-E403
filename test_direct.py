import asyncio
import os
os.environ["ENABLE_LLM"] = "true"
from coach.api import summarize_lesson, SummarizeRequest

async def main():
    req = SummarizeRequest(lesson_id="day1")
    res = await summarize_lesson(req)
    print("Result:", res)

asyncio.run(main())
