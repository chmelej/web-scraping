import asyncio
from crawlee.crawlers import PlaywrightCrawler
from crawlee import Request

async def main():
    async def request_handler(context):
        try:
            user_data = context.request.user_data
            # Test item access
            print(f"Queue ID item: {user_data['queue_id']}")
        except Exception as e:
            print(f"Error accessing user_data item: {e}")
            # Try attribute access
            try:
                print(f"Queue ID attr: {user_data.queue_id}")
            except Exception as e2:
                print(f"Error accessing user_data attr: {e2}")

    crawler = PlaywrightCrawler(request_handler=request_handler, max_requests_per_crawl=1, headless=True)
    await crawler.run([Request.from_url("https://example.com", user_data={"queue_id": 123})])

if __name__ == "__main__":
    asyncio.run(main())
