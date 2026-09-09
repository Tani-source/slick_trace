# 🚀 SlickTrace Free Deployment Guide ($0 / Month)

This guide shows you how to deploy the entire SlickTrace application (React 18 + Vite frontend and FastAPI + Geospatial/ML backend) **100% free of charge**, with **no credit card required**.

---

## 🏆 Summary of Free Deployment Options

| Platform | Frontend | Backend | Specs | Free Tier Cost | Best For |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Hugging Face Spaces** *(Recommended)* | Unified (Docker) | Unified (Docker) | **16 GB RAM**, 2 vCPUs, 50 GB disk | **$0 forever** (No CC) | **Heavy ML/Geo workloads (PyTorch, GeoPandas)** |
| **Vercel + Render / HF** | Vercel | Render or HF Spaces | High-speed Global Edge CDN + Cloud Python | **$0 forever** (No CC) | **Fastest frontend load times** |
| **Render Web Service** | Unified (Docker) | Unified (Docker) | 512 MB RAM, 0.1 vCPU | **$0 forever** (No CC) | Simple single-service setup |
| **Cloudflare Tunnel** | Localhost | Localhost | Your Mac hardware | **$0 forever** | Instant live demo / Hackathon presentation |

---

## 🥇 Option 1: Hugging Face Spaces (Recommended — 16 GB RAM Free)

Because SlickTrace uses **PyTorch, NumPy, SciPy, and GeoPandas**, standard free tiers like Render (512 MB RAM) can occasionally run into memory limits during heavy advection calculations. **Hugging Face Spaces provides 16 GB of RAM and 2 vCPUs completely free**.

The repository now includes a **multi-stage `Dockerfile`** that builds both the React Vite frontend and FastAPI backend into a single container.

### Step-by-Step:
1. **Push your code to GitHub** (if not already pushed):
   ```bash
   git add .
   git commit -m "Add production deployment configs"
   git push origin main
   ```
2. Go to [huggingface.co/new-space](https://huggingface.co/new-space) (create a free account if you don't have one).
3. Fill in:
   - **Space Name:** `slicktrace`
   - **License:** `mit` (or choose your preferred license)
   - **Space SDK:** Choose **`Docker`** -> **`Blank`**
   - **Space Hardware:** Select **`CPU basic • 2 vCPU • 16 GB RAM • Free`**
   - **Visibility:** `Public`
4. Click **Create Space**.
5. Connect your GitHub repository under Space **Settings > GitHub integration**, or push using the Hugging Face Git remote:
   ```bash
   git remote add hf https://huggingface.co/spaces/<YOUR-USERNAME>/slicktrace
   git push hf main
   ```
6. **Done!** Hugging Face will automatically build the Docker container and launch the app at:
   `https://<YOUR-USERNAME>-slicktrace.hf.space`

---

## 🥈 Option 2: Decoupled Setup (Vercel Frontend + Hugging Face or Render Backend)

If you want the frontend to load instantaneously from Vercel's global CDN:

### Part A: Deploy Backend to Render or Hugging Face
1. Deploy the backend using Docker on Hugging Face (as above) or Render.
2. Note your backend URL (e.g. `https://your-app.hf.space` or `https://slicktrace-api.onrender.com`).

### Part B: Deploy Frontend to Vercel (100% Free)
1. Go to [vercel.com/new](https://vercel.com/new) and import your GitHub repository.
2. Set the following project settings:
   - **Framework Preset:** `Vite`
   - **Root Directory:** `frontend`
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
3. Add an Environment Variable:
   - **Key:** `VITE_API_URL`
   - **Value:** Your backend URL (e.g., `https://your-app.hf.space`)
4. Click **Deploy**. Vercel will build the frontend in ~15 seconds and provide a `https://slicktrace.vercel.app` URL.

---

## 🥉 Option 3: Render (Free Web Service via Docker)

Render offers a free Web Service tier:
1. Go to [dashboard.render.com](https://dashboard.render.com) and click **New > Web Service**.
2. Connect your GitHub repository.
3. Choose **Docker** as the runtime.
4. Select the **Free** instance type (512 MB RAM).
5. (Optional) In Advanced settings, set health check path to `/api/health`.
6. Click **Create Web Service**.

> **Note on Render Free Tier:** Render spins down free web services after 15 minutes of inactivity. When a new request arrives, it takes ~50 seconds to wake up (cold start). Hugging Face Spaces or Vercel are typically faster.

---

## ⚡ Option 4: Instant Live Demo via Cloudflare Tunnel ($0 / 0 Cloud Setup)

If you have a live hackathon demo or interview and want to demo the live app running directly from your computer without uploading anywhere:

1. Install Cloudflare `cloudflared`:
   ```bash
   brew install cloudflared
   ```
2. Start the SlickTrace backend and frontend:
   ```bash
   # Terminal 1:
   cd backend
   python3 -m uvicorn app.main:app --port 8000

   # Terminal 2:
   cd frontend
   npm run dev
   ```
3. Expose it with a single command:
   ```bash
   cloudflared tunnel --url http://localhost:5173
   ```
4. You will instantly receive a public `https://xxxx.trycloudflare.com` URL that anyone in the world can open on their laptop or phone.

---

## 🔧 Technical Enhancements Applied to this Repo

- ✅ **Unified Serving:** FastAPI now automatically detects and serves Vite production assets in `frontend/dist` at `/`, eliminating CORS headaches and eliminating the need for separate hosting.
- ✅ **Dynamic API Resolution:** `frontend/src/api/client.ts` automatically adapts to local dev proxying, unified single-service hosting (`/api`), or custom `VITE_API_URL`.
- ✅ **Optimized Multi-Stage Dockerfile:** Uses CPU-only PyTorch (`--index-url https://download.pytorch.org/whl/cpu`) saving 2.5 GB of download size and memory overhead.
- ✅ **Fast Production Bundling:** Vite build script configured to create minified assets in under 200ms.
