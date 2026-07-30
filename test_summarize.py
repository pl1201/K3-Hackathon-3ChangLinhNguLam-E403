import asyncio
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://127.0.0.1:8000/api/summarize",
            json={"lesson_id": "day1"}
        )
        print("Status Code:", resp.status_code)
        print("Response:", resp.json())

asyncio.run(main())
