from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .routers import queue, dashboard
import os

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

# Serve the static Vue frontend files if they exist
web_dist_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "web", "dist")

if os.path.isdir(web_dist_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(web_dist_dir, "assets")), name="assets")

    # Serve index.html for all other routes to support Vue Router in HTML5 mode
    @app.get("/{full_path:path}")
    async def serve_vue_app(full_path: str):
        index_file = os.path.join(web_dist_dir, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file)
        return {"error": "Frontend not built. Run npm run build in web/ directory."}
