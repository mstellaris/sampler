# Bookmark Saver

A minimal bookmark saving app — FastAPI backend, Nginx frontend, SQLite storage, all orchestrated with Docker Compose.

## Project Structure

```
├── docker-compose.yml
├── backend/
│   ├── Dockerfile
│   ├── main.py            # FastAPI app with CRUD endpoints
│   └── requirements.txt
└── frontend/
    ├── Dockerfile          # Nginx-based
    ├── nginx.conf          # Proxies /api → backend
    └── public/
        ├── index.html
        ├── style.css
        └── app.js
```

## Run Locally

```bash
docker compose up --build
```

Open [http://localhost:8080](http://localhost:8080) in your browser.

## API Endpoints

| Method   | Path                     | Description       |
|----------|--------------------------|-------------------|
| `GET`    | `/api/bookmarks`         | List all bookmarks |
| `POST`   | `/api/bookmarks`         | Create a bookmark  |
| `DELETE`  | `/api/bookmarks/{id}`   | Delete a bookmark  |

**POST body:**
```json
{ "url": "https://example.com", "title": "Example" }
```

## Deploy on Synology NAS

1. **Copy the project** to your NAS (e.g. via SSH, shared folder, or Git).

2. **SSH into your NAS** and navigate to the project directory.

3. **Run:**
   ```bash
   docker compose up --build -d
   ```

4. **Access** the app at `http://<nas-ip>:8080`.

Alternatively, use **Container Manager** (DSM 7.2+):
- Open Container Manager → Project → Create
- Set the path to the folder containing `docker-compose.yml`
- Click Build & Start

## Data Persistence

Bookmarks are stored in a Docker volume (`bookmarks-data`). Your data survives container restarts and rebuilds.
