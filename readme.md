# FastAPI HTML to PDF Microservice

A FastAPI-based microservice for converting HTML content into PDF documents using **Playwright** and **Chromium**. The service supports both uploaded HTML files and raw HTML strings, producing high-quality PDFs with full support for modern HTML, CSS, JavaScript, images, and web fonts.

The service is designed to run reliably in both development and production environments, including headless Linux servers, Windows machines, Docker containers, CI/CD runners, and cloud virtual machines.

---

# Features

- Convert uploaded HTML files (`.html` / `.htm`) to PDF
- Convert raw HTML strings to PDF
- High-fidelity rendering using Chromium
- Supports modern HTML, CSS and JavaScript
- Headless operation (no GUI required)
- REST API powered by FastAPI
- Interactive Swagger documentation
- Production-ready

---

# Project Structure

```
.
├── app.py                  # FastAPI application
├── functions.py            # API implementation
├── requirements.txt
├── README.md
└── ...
```

---

# Requirements

- Python 3.10+
- Playwright
- Chromium (installed via Playwright)

---

# Installation

## 1. Clone the Repository

```bash
git clone <repository-url>
cd python-fastapi-microservices
```

---

## 2. Create a Virtual Environment

### Linux

```bash
python3 -m venv python-fastapi-microservices-venv

source python-fastapi-microservices-venv/bin/activate
```

### Windows

```powershell
python -m venv python-fastapi-microservices-venv

python-fastapi-microservices-venv\Scripts\activate
```

---

## 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

---

# Playwright Installation

Install the Chromium browser used for rendering PDFs.

```bash
playwright install chromium
```

or

```bash
python -m playwright install chromium
```

---

# Playwright Dependencies

## Linux (Ubuntu, EC2, Docker, Headless Servers)

Playwright requires additional system libraries for Chromium.

### Recommended

```bash
sudo playwright install-deps
```

or

```bash
python -m playwright install-deps
```

### Manual Installation (Ubuntu)

If automatic installation is unavailable:

```bash
sudo apt update

sudo apt install -y \
    libxcb-shm0 \
    libx11-xcb1 \
    libxrandr2 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxi6 \
    libxfixes3 \
    libgtk-3-0 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libatk1.0-0 \
    libcairo-gobject2 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libxrender1 \
    libasound2
```

---

## Windows

No additional system dependencies are required.

Simply install Playwright and Chromium:

```powershell
pip install -r requirements.txt

playwright install chromium
```

---

# Running the Application

Start the development server:

```bash
uvicorn app:app --reload
```

The application will be available at:

```
http://localhost:8000
```

Swagger UI:

```
http://localhost:8000/docs
```

---

# Production Deployment

The recommended production architecture is:

```
                    Internet
                        │
                        ▼
                     Nginx
                        │
                        ▼
      Gunicorn (Uvicorn Workers)
                        │
                        ▼
                     FastAPI
                        │
                        ▼
           Playwright + Chromium
```

Recommended production components:

- **Reverse Proxy:** Nginx
- **Application Server:** Gunicorn
- **Worker Class:** `uvicorn.workers.UvicornWorker`
- **Browser Engine:** Chromium
- **Process Manager (Linux):** systemd

### Gunicorn

Example command:

```bash
gunicorn app:app \
    -k uvicorn.workers.UvicornWorker \
    --workers 4 \
    --bind 127.0.0.1:8000
```

The recommended number of workers depends on the available CPU cores and expected workload. Since each conversion launches a headless Chromium instance, avoid configuring significantly more workers than the server can comfortably support.

### Unix Socket (Recommended)

If **Nginx and the FastAPI application are running on the same machine**, it is recommended to bind Gunicorn to a **Unix domain socket** instead of a TCP port. Unix sockets provide slightly better performance and eliminate the need to expose a local network port.

Example:

```bash
gunicorn app:app \
    -k uvicorn.workers.UvicornWorker \
    --workers 4 \
    --bind unix:/run/fastapi/fastapi.sock
```

Configure Nginx to proxy requests to the same Unix socket.

---

# API Endpoints

## Health Check

### Request

```
GET /health
```

### Response

```json
{
    "status": "ok"
}
```

---

## Convert HTML to PDF

### Request

```
POST /convert_html
```

Content-Type:

```
multipart/form-data
```

The endpoint accepts **exactly one** of the following:

### Option 1 — Upload an HTML File

| Parameter | Type | Description |
|-----------|------|-------------|
| file | File | HTML (.html/.htm) file |

---

### Option 2 — Raw HTML

| Parameter | Type | Description |
|-----------|------|-------------|
| html | String | Raw HTML content |

---

### Response

Returns:

```
application/pdf
```

---

# Swagger Documentation

Development:

```
http://localhost:8000/docs
```

Production (behind reverse proxy):

```
https://<domain>/fastapi/docs
```

---

# Common Issues

## Chromium Not Installed

Error:

```
Executable doesn't exist
```

Install Chromium:

```bash
playwright install chromium
```

---

## Missing Linux Dependencies

Error:

```
Host system is missing dependencies
```

Install the required libraries:

```bash
sudo playwright install-deps
```

---

## Chromium Crashes on Headless Linux

When launching Chromium, use the following arguments:

```python
browser = await p.chromium.launch(
    headless=True,
    args=[
        "--no-sandbox",
        "--disable-dev-shm-usage",
    ],
)
```

These options are recommended for:

- Linux servers
- EC2 instances
- Docker containers
- Kubernetes
- CI/CD runners
- Virtual machines

---

# Useful Commands

Install project dependencies:

```bash
pip install -r requirements.txt
```

Install Chromium:

```bash
playwright install chromium
```

Install Linux browser dependencies:

```bash
sudo playwright install-deps
```

Run locally:

```bash
uvicorn app:app --reload
```

Run in production:

```bash
gunicorn app:app \
    -k uvicorn.workers.UvicornWorker \
    --workers 4 \
    --bind 127.0.0.1:8000
```

---

# Notes

- Chromium is automatically managed by Playwright.
- No graphical desktop environment is required.
- The service works on Windows, Linux, Docker, and cloud virtual machines.
- Playwright provides significantly better rendering quality than traditional HTML-to-PDF libraries by using Chromium's native rendering engine.
- Modern CSS, JavaScript, images, SVGs, and web fonts are fully supported.