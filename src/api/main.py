from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import queue, dashboard

app = FastAPI(
    title="Web Scraper API",
    description="API for accessing and managing web scraper data",
    version="1.0.0",
)

# Enable CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins, adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(queue.router, prefix="/api/v1/queue", tags=["queue"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["dashboard"])

@app.get("/api/v1/health")
async def health_check():
    return {"status": "healthy"}
