# SpotifyWebQuiz

A production-ready musical quiz game built with **FastAPI**, **Jinja2**, **Tailwind CSS**, and the **Spotify Web Playback SDK**. Players listen to tracks from their own Spotify playlists and must guess the correct song from four options within a 15-second countdown.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Game Mechanics](#game-mechanics)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [How It Works](#how-it-works)
- [API Endpoints](#api-endpoints)
- [Project Structure](#project-structure)
- [Security Notes](#security-notes)

---

## Features

- **Spotify OAuth2 Integration** — Full authorization flow with automatic token refresh.
- **Server-Side Sessions** — All game state and tokens stored in secure, signed cookies. The frontend never sees the correct answer before submitting.
- **Anti-Cheat Validation** — Correctness is determined exclusively by the backend. The frontend only receives track names and artists; album covers are hidden until the round ends.
- **Combo / Fever Mode** — Consecutive correct answers build a combo multiplier. At combo ≥ 3, "Fever Mode" activates: neon green screen-border pulse and doubled points.
- **Panic Mode** — When the timer drops below 4 seconds, UI accents shift to warning lime-yellow and the CSS equalizer animation doubles in speed.
- **Endgame Analytics** — Results screen displays:
  - **Your Anthem** — The track guessed with the fastest reaction time.
  - **Your Kryptonite** — The track where you made a mistake or timed out with the longest duration.
- **Cyber-Emerald UI** — Deep matte black (`#050505`) base, neon Spotify green (`#1DB954`) accents, glassmorphism containers, and smooth CSS animations.

---

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────────┐
│   Browser   │◄────►│  FastAPI App │◄────►│  Spotify API    │
│  (SDK Player)│      │  (Python 3.10+)│     │  (OAuth + Web)  │
└─────────────┘      └──────────────┘      └─────────────────┘
```

- **Backend**: FastAPI with async `httpx` for non-blocking Spotify API calls.
- **Frontend**: Jinja2 HTML templates, Tailwind CSS (CDN), Alpine.js (CDN) for lightweight reactivity, and the official Spotify Web Playback SDK for audio streaming.
- **State Management**: Signed session cookies (`itsdangerous`) store OAuth tokens and the full `GameSession` object server-side.

---

## Game Mechanics

### Round Flow

1. **Initialization** — The backend fetches all tracks from the selected playlist, filters out local files and tracks without valid `spotify:track:` URIs, and stores them in the session.
2. **Round Generation** — For each of 10 rounds, the backend randomly selects:
   - 1 **target track** (the one that will play).
   - 3 **decoy tracks** from the same playlist.
3. **Template Rendering** — The backend passes to the frontend:
   - The target track's **URI** (so the SDK can play it).
   - An **obfuscated list of 4 options** containing only `id`, `name`, and `artist`. No album covers, no correctness flags.
4. **Playback** — The frontend initializes the Spotify Web Playback SDK, receives a `device_id`, and calls the Spotify Web API to start playback. A 1000 ms safety timeout ensures the device is ready.
5. **Countdown** — A 15-second timer runs. An animated CSS equalizer pulses inside the timer circle while the SDK reports `playing` state.
6. **Answer Submission** — When the user clicks a card:
   - The player pauses immediately.
   - An async `POST /api/check-answer` sends the chosen `id` and elapsed milliseconds to the backend.
   - The backend checks the choice against the server-stored `current_target_id`.
   - The backend returns: `correct`, `points`, `combo`, `fever_mode`, `total_score`, `correct_id`, `album_cover`, `track_name`, `artist_name`.
7. **Visual Feedback** —
   - **Correct**: Card flashes neon green, particle effect triggers, album art reveals from `blur-xl`.
   - **Incorrect**: Chosen card shakes and flashes red; correct card highlights in green; album art reveals.
8. **Transition** — A 3-second freeze displays the result, then the frontend fetches the next round via `GET /api/next-round` and seamlessly transitions.

### Scoring

- **Base points** = `max(0, 200 - floor(elapsed_ms / 100))`
- **Combo multiplier** = `1 + combo * 0.5` (x1, x1.5, x2, x2.5...)
- **Fever Mode** (combo ≥ 3): multiplier doubled.
- Wrong answer or timeout: 0 points, combo resets to 0.

---

## Prerequisites

- Python 3.10+
- A **Spotify Premium** account (required for Web Playback SDK streaming).
- A registered **Spotify App** at [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard).

---

## Installation

```bash
# 1. Clone or navigate into the project directory
cd spotigame

# 2. Create a virtual environment (recommended)
python -m venv venv

# 3. Activate it
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt
```

---

## Configuration

Create a `.env` file in the project root (see `.env.example`):

```env
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SECRET_KEY=a_strong_random_secret_at_least_32_chars
```

### Spotify App Settings

In your Spotify app dashboard, add this **Redirect URI**:

```
http://localhost:8000/callback
```

> **Note**: If you deploy to a public domain, update `SPOTIFY_REDIRECT_URI` in `app/config.py` accordingly.

---

## Running the Application

```bash
# Development (with auto-reload)
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production (using a proper ASGI server like gunicorn)
gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

Open your browser at **http://localhost:8000**.

---

## How It Works

### Authentication Flow

1. User clicks **"Login with Spotify"** on the landing page.
2. Backend redirects to Spotify's OAuth authorize URL with scopes:
   - `user-read-private`, `user-read-email`
   - `streaming`, `user-read-playback-state`, `user-modify-playback-state`
3. Spotify redirects back to `/callback` with an authorization `code`.
4. Backend exchanges the code for `access_token` + `refresh_token` and stores both in a signed session cookie.
5. On every subsequent request, the backend reads the cookie, refreshes the token if expired, and injects the token into API calls.

### Playlist Selection (`/`)

- If unauthorized → cinematic login page.
- If authorized → backend fetches `GET /v1/me/playlists`, filters out playlists with fewer than 10 tracks, and renders a responsive grid of playlist cards.

### Game Arena (`/game/{playlist_id}`)

- Loads the playlist's tracks into the server-side `GameSession`.
- Generates rounds server-side; the frontend only receives obfuscated options.
- The Spotify Web Playback SDK is initialized with the user's `access_token`.
- Once `ready`, the SDK provides a `device_id`; the backend (via frontend JS) calls `PUT /v1/me/player/play` to start the target track.

### Results (`/results`)

- Displays final score, accuracy percentage, "Your Anthem", and "Your Kryptonite" with high-resolution album art.
- A pulsing "Play Again" button resets the session game state and redirects to `/`.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Dashboard / Playlist selection (or login page) |
| `GET` | `/login` | Redirect to Spotify OAuth authorization |
| `GET` | `/callback` | OAuth callback — exchanges code for tokens |
| `POST` | `/api/refresh-token` | Refresh Spotify access token manually |
| `GET` | `/logout` | Clear session and redirect home |
| `GET` | `/game/{playlist_id}` | Initialize / resume game arena (HTML) |
| `POST` | `/api/check-answer` | Validate user's card choice (anti-cheat) |
| `GET` | `/api/next-round` | Generate and return next round data (JSON) |
| `GET` | `/results` | Endgame analytics screen (HTML) |

---

## Project Structure

```
spotigame/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app factory, middleware, static files
│   ├── config.py               # Pydantic Settings (env vars)
│   ├── dependencies.py         # Session cookie helpers
│   ├── models/
│   │   ├── __init__.py
│   │   └── session.py          # GameSession & RoundResult dataclasses
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py             # OAuth2 login, callback, refresh, logout
│   │   ├── dashboard.py         # Playlist grid rendering
│   │   └── game.py             # Game arena, answer validation, results
│   ├── services/
│   │   ├── __init__.py
│   │   ├── spotify.py          # Async Spotify API client (httpx)
│   │   └── game_logic.py       # Round generation & scoring engine
│   └── templates/
│       ├── base.html             # Base layout (Tailwind + Alpine.js)
│       ├── login.html            # Cinematic landing page
│       ├── dashboard.html        # Playlist selection grid
│       ├── game.html             # Game arena (SDK + timer + cards)
│       └── results.html          # Endgame analytics
├── static/
│   └── css/
│       └── custom.css            # Cyber-Emerald animations & glassmorphism
├── .env                          # Environment variables (gitignored)
├── .env.example                  # Example environment file
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

---

## Security Notes

- **Never expose the correct answer in the frontend** during an active round. The template only receives `id`, `name`, and `artist` for each option. Correctness is resolved server-side at `POST /api/check-answer`.
- **Session cookies are signed** with `itsdangerous` using the `SECRET_KEY`. They are not encrypted by default; deploy behind HTTPS in production.
- **Token refresh** is handled automatically by middleware and also exposed at `POST /api/refresh-token` for manual frontend refresh if needed.
- **No database required** — all state lives in signed cookies, making the app lightweight and stateless across restarts (though sessions are lost on server restart).

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python 3.10+, FastAPI, Pydantic, httpx |
| Frontend | Jinja2, Tailwind CSS (CDN), Alpine.js (CDN) |
| Audio | Spotify Web Playback SDK (JavaScript) |
| Auth | Spotify OAuth2 + itsdangerous signed cookies |

---

## License

MIT
