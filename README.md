# Sampler

A bookmark saving app with automatic screenshot capture and LinkedIn post scraping. Built with FastAPI, Nginx, SQLite, and Docker Compose.

## Features

- **Bookmark Management** — Save, list, and delete bookmarks with a clean web UI
- **Screenshot Previews** — Automatically captures a screenshot of each bookmarked page using Playwright
- **LinkedIn Post Scraping** — Detects LinkedIn URLs and extracts post content, author info, and images using authenticated sessions
- **Persistent Storage** — SQLite database and screenshots stored in a Docker volume

## Project Structure

```
├── .github/workflows/build.yml   # CI/CD — builds & pushes to GHCR
├── docker-compose.yml             # Development
├── docker-compose.prod.yml        # Production (pulls from GHCR)
├── .env                           # LinkedIn credentials (optional)
├── backend/
│   ├── Dockerfile
│   ├── main.py                    # FastAPI app
│   └── requirements.txt
└── frontend/
    ├── Dockerfile                 # Nginx-based
    ├── nginx.conf                 # Proxies /api → backend
    └── public/
        ├── index.html
        ├── style.css
        └── app.js
```

## Run Locally

```bash
docker compose up --build
```

Open [http://localhost:9090](http://localhost:9090) in your browser.

### LinkedIn Scraping (Optional)

Create a `.env` file with your LinkedIn credentials:

```
LINKEDIN_EMAIL=your-email@example.com
LINKEDIN_PASSWORD=your-password
```

If not provided, bookmarks are still saved — LinkedIn content extraction is skipped.

## API Endpoints

| Method   | Path                                            | Description                |
|----------|-------------------------------------------------|----------------------------|
| `GET`    | `/api/bookmarks`                                | List all bookmarks         |
| `POST`   | `/api/bookmarks`                                | Create a bookmark          |
| `DELETE` | `/api/bookmarks/{id}`                           | Delete a bookmark          |
| `GET`    | `/api/screenshots/{id}`                         | Get screenshot image       |
| `GET`    | `/api/linkedin-images/{id}/{filename}`          | Get LinkedIn post image    |

**POST body:**
```json
{ "url": "https://example.com", "title": "Example" }
```

## Production

Pull pre-built images from GitHub Container Registry:

```bash
docker compose -f docker-compose.prod.yml up -d
```

## Deploy on Synology NAS

1. Copy the project to your NAS (via SSH, shared folder, or Git).
2. SSH into your NAS and navigate to the project directory.
3. Run:
   ```bash
   docker compose up --build -d
   ```
4. Access the app at `http://<nas-ip>:9090`.

Or use **Container Manager** (DSM 7.2+):
- Open Container Manager → Project → Create
- Set the path to the folder containing `docker-compose.yml`
- Click Build & Start

## CI/CD

GitHub Actions automatically builds and pushes multi-platform images (`linux/amd64`, `linux/arm64`) to GHCR on every push to `main`:

- `ghcr.io/mstellaris/sampler-backend:latest`
- `ghcr.io/mstellaris/sampler-frontend:latest`

## Data Persistence

All data is stored in a Docker volume (`bookmarks-data`) and survives container restarts:

- SQLite database (`bookmarks.db`)
- Screenshots (`screenshots/`)
- LinkedIn images (`linkedin-images/`)
