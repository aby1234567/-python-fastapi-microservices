from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.middleware.cors import CORSMiddleware
import functions as f

app = FastAPI(title = "R7 fastapi-microservices",
              root_path="/fastapi",
                version="1.0.0",
                docs_url=None,
                redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # allow from anywhere
    allow_credentials=False,      # MUST be False to use "*"
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],          # or explicitly: ["Authorization", "Content-Type"]
    expose_headers=["*"],         # optional
)

@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI is running successfully!"}

@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=f"{app.root_path}{app.openapi_url}",
        title="R7 fastapi-microservices",
        swagger_favicon_url="https://www.rubyseven.in/wp-content/uploads/2025/08/cropped-Logo-1.png",
    )

app.add_api_route("/health", f.health, methods=["GET"],response_model=f.HealthResponse, tags=["pdf"])
app.add_api_route("/convert_html", f.convert, methods=["POST"],response_class=f.FileResponse, tags=["pdf"])
