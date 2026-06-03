# StegoVault 🔐

A steganography web app that lets you:
- **Hide secret messages** inside images (LSB encoding)
- **Decode hidden messages** from images
- **Sign up & log in** using both a text password AND an image password (dual-factor)

---

**Core concepts:** https://drive.google.com/file/d/15phTVzwHr11rwgvKUWbsCnBDHe1_903Q/view?usp=sharing

**Testing video:** https://drive.google.com/file/d/1QSZ1QkHw2tYfWaVxqweUGUI7NIg6B4RM/view?usp=sharing

## Tech Stack

| Layer     | Tech                            |
|-----------|---------------------------------|
| Backend   | Python · FastAPI · SQLite       |
| Frontend  | Vanilla HTML/CSS/JS (no build)  |
| Crypto    | bcrypt · JWT · SHA-256          |
| Stego     | LSB (Least-Significant Bit)     |

---

## 🚀 Run Locally (Option A — Pure Python, no Docker)

### 1. Clone / unzip the project
```bash
cd stegoapp
```

### 2. Set up the Python backend
```bash
cd backend
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows (PowerShell)
venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 3. Start the backend
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
API is now live at http://localhost:8000  
Swagger docs: http://localhost:8000/docs

### 4. Serve the frontend
Open a new terminal in the `frontend/` folder:

```bash
# Python 3 built-in server (simplest)
python -m http.server 3000
```

App is now live at **http://localhost:3000**

---

## 🐳 Run Locally (Option B — Docker Compose)

Requires Docker Desktop installed.

```bash
# From the project root (stegoapp/)
docker-compose up --build
```

- Frontend → http://localhost:3000
- Backend  → http://localhost:8000

---

## 📁 Project Structure

```
stegoapp/
├── backend/
│   ├── main.py            # FastAPI app (auth + steganography)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── stegoapp.db        # SQLite DB (auto-created on first run)
├── frontend/
│   └── index.html         # Full single-page app
└── docker-compose.yml
```

---

## 🌍 Deploy for Free

### Backend → Render.com (free tier)

1. Push project to a **GitHub** repository
2. Go to [render.com](https://render.com) → New → **Web Service**
3. Connect your repo, select the `backend/` folder
4. Settings:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add environment variable: `SECRET_KEY` → any random string
6. Deploy → copy your URL (e.g. `https://stegovault-api.onrender.com`)

> ⚠️ Free Render services sleep after 15 min of inactivity. First request may take ~30s.

---

### Frontend → GitHub Pages (free, instant)

1. Edit `frontend/index.html` line:
   ```js
   const API = 'https://stegovault-api.onrender.com'; // ← your Render URL
   ```
2. Push `frontend/` to GitHub
3. Go to repo **Settings → Pages → Source: main branch / root**
4. Your app is live at `https://<yourname>.github.io/<repo>/frontend/`

---

### Alternative: Netlify (frontend, even easier)

1. Go to [netlify.com](https://netlify.com) → **Add new site → Deploy manually**
2. Drag and drop your `frontend/` folder
3. Done — instant URL, free SSL

---

### Alternative: Railway.app (backend)

1. Connect GitHub at [railway.app](https://railway.app)
2. New project → Deploy from GitHub → select `backend/` folder
3. Add `SECRET_KEY` env var
4. Railway auto-detects Python and deploys

---

## 🔐 How the Image Password Works

When you sign up, the app:
1. Resizes your image to 64×64 px
2. Computes a **SHA-256 hash** of the pixel bytes
3. Stores that hash (never the image itself)

At login, the same hash is computed from the uploaded image and compared. The image must be **identical** to the signup image.

---

## 🧩 How Steganography Works (LSB)

Each pixel in an RGB image has 3 channels (R, G, B), each 0–255. The **least-significant bit** of each value contributes almost nothing visually. The app:
1. Converts your message to binary
2. Replaces the last bit of each channel value with message bits
3. Appends a `<<<END>>>` delimiter
4. Saves as lossless PNG (important — JPEG would destroy the hidden data)

The output image looks **visually identical** to the original.
