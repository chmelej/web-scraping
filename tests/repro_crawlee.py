import asyncio
import logging
from crawlee.crawlers import PlaywrightCrawler
from crawlee import Request

async def main():
    print("Starting crawler test...")

    async def request_handler(context):
        print(f"Handling request: {context.request.url}")

        # Test accessing user_data
        try:
            # Pydantic model access
            user_data = context.request.user_data
            print(f"User data type: {type(user_data)}")
            print(f"User data content: {user_data}")

            queue_id = user_data.get('queue_id') # Assuming dict-like
            print(f"Queue ID: {queue_id}")

        except Exception as e:
            print(f"Error accessing user_data: {e}")
            print(f"Request attributes: {dir(context.request)}")

    crawler = PlaywrightCrawler(
        request_handler=request_handler,
        max_requests_per_crawl=1,
        headless=True,
    )

    # Correct usage with Request objects
    request_list = [
        Request.from_url(url="https://example.com", user_data={"queue_id": 123, "retry_count": 0})
    ]

    await crawler.run(request_list)
    print("Crawler finished.")

if __name__ == "__main__":
    asyncio.run(main())
