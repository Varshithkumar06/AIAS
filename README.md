# AIAS

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1.1-000000?style=flat-square&logo=flask&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-47A248?style=flat-square&logo=mongodb&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-5.0-DC382D?style=flat-square&logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED?style=flat-square&logo=docker&logoColor=white)
[![Azure Container Apps](https://img.shields.io/badge/Live_Deployment-Azure_Container_Apps-0078D4?style=flat-square&logo=microsoftazure&logoColor=white)](https://aias-web-standard.bluedune-52554353.southeastasia.azurecontainerapps.io/)

> 🌐 **Live Production URL:** [https://aias-web-standard.bluedune-52554353.southeastasia.azurecontainerapps.io/](https://aias-web-standard.bluedune-52554353.southeastasia.azurecontainerapps.io/)

AIAS is a Flask-based business website and lead management platform. It provides a public website, secure user authentication, an Aria chatbot for lead capture, booking workflows, admin operations, MongoDB Atlas database persistence, Redis caching, email notifications, Zoom meeting support, and Docker-based deployment.

## Project Summary

AIAS includes:

- Public AIAS homepage
- User registration and sign-in
- Password reset with OTP
- Google OAuth sign-in
- Aria chatbot for lead qualification
- Booking capture for voice and video calls
- Zoom meeting creation for video consultations
- Email notifications through Gmail SMTP
- Admin dashboard for users, leads, security logs, Redis cache, database schema, and scheduling
- MongoDB Atlas database persistence
- Redis caching and rate limiting
- Docker deployment with a web container and Redis container

## Main Technology Stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.12, Flask |
| Auth helpers | Flask-Bcrypt, Flask-WTF CSRF, Authlib |
| Database | MongoDB Atlas through `pymongo` |
| Cache/rate limiting | Redis |
| Email | Gmail SMTP |
| Video meetings | Zoom Server-to-Server OAuth |
| Frontend | Jinja templates, HTML, CSS, vanilla JavaScript |
| Production server | Gunicorn |
| Deployment | Docker, Docker Compose |

## Project Structure

```text
AIAS/
  app.py
  config.py
  requirements.txt
  Dockerfile
  docker-compose.yml
  .dockerignore
  .gitignore
  .env.example
  information.md
  README.md

  auth/
    routes.py
    email_service.py
    google_oauth.py
    otp_service.py
    rate_limiter.py
    redis_service.py
    zoom_service.py

  database/
    db.py
    models.py
    security.py

  static/
    css/signin.css
    js/signin.js
    js/auth_features.js
    js/chatbot.js
    images/logo.png

  templates/
    homepage.html
    signin.html
    register.html
    verify_otp.html
    forgot_password.html
    reset_password.html
    dashboard.html
    admin.html
```

## Core Files

| File | Responsibility |
| --- | --- |
| `app.py` | Main Flask app factory, public routes, admin routes, booking endpoint, Redis/admin integrations, and cleanup hooks |
| `config.py` | Central environment/config loader for Flask, database, Redis, email, Google OAuth, and Zoom |
| `auth/routes.py` | Authentication blueprint for sign-in, registration, OTP, password reset, Google OAuth, sign-out, and dashboard |
| `auth/email_service.py` | Outbound OTP, welcome, booking, and notification emails |
| `auth/otp_service.py` | OTP generation, hashing, verification, expiry, and attempt handling |
| `auth/rate_limiter.py` | Login and OTP request limiting helpers |
| `auth/redis_service.py` | Redis client, session cache helpers, and rate-limit helpers |
| `auth/google_oauth.py` | Google OAuth client setup |
| `auth/zoom_service.py` | Zoom access token and meeting creation integration |
| `database/db.py` | MongoDB connection manager, indexes, and admin query helpers |
| `database/models.py` | User, OTP, and session data access models |
| `database/security.py` | Maintenance helpers, cleanup tasks, and health checks |
| `templates/homepage.html` | Public AIAS homepage |
| `templates/admin.html` | Admin dashboard UI |
| `static/js/chatbot.js` | Aria chatbot lead and booking flow |

## Database Tables

| Table | Purpose |
| --- | --- |
| `users` | Registered users, verification state, Google OAuth state, and login lockout data |
| `otp_codes` | Hashed OTP codes for registration and password reset |
| `sessions` | Login session records |
| `rate_limit_log` | Auth and rate-limit activity records |
| `bookings` | Chatbot leads, contact details, booking status, scheduled calls, and meeting links |

## High-Level Architecture

```mermaid
flowchart LR
    U["Website User"] --> H["Homepage"]
    U --> A["Auth Pages"]
    H --> C["Aria Chatbot"]
    C --> B["Booking API"]
    A --> AR["Auth Blueprint"]
    Admin["Admin User"] --> AD["Admin Dashboard"]

    B --> DB["MongoDB Atlas"]
    AR --> DB
    AD --> DB

    AR --> R["Redis Cache"]
    AD --> R
    App["Flask App"] --> R

    B --> E["Gmail SMTP"]
    AR --> E
    AD --> E

    B --> Z["Zoom API"]
    AD --> Z
```

## Request Lifecycle

```mermaid
sequenceDiagram
    participant Browser
    participant Flask
    participant Redis
    participant MongoDB

    Browser->>Flask: HTTP request
    Flask->>Redis: Check request/session cache when needed
    Redis-->>Flask: Cache or limit result

    alt Request accepted
        Flask->>MongoDB: Read/write application data
        MongoDB-->>Flask: Query result
        Flask-->>Browser: HTML or JSON response
    else Request limited
        Flask-->>Browser: Rate limit response
    end
```

## Authentication Workflow

```mermaid
flowchart TD
    Start["User opens sign-in"] --> Method{"Login method"}
    Method --> Password["Email and password"]
    Method --> Google["Google OAuth"]
    Password --> Rate["Check login limits"]
    Rate --> Exists{"User exists?"}
    Exists -- No --> Error["Show sign-in error"]
    Exists -- Yes --> Locked{"Account locked?"}
    Locked -- Yes --> LockMsg["Show lockout message"]
    Locked -- No --> Valid{"Password valid?"}
    Valid -- No --> Failed["Record failed attempt"]
    Valid -- Yes --> Session["Create session"]
    Google --> OAuth["Verify Google profile"]
    OAuth --> Session
    Session --> Cache["Cache session in Redis"]
    Cache --> Home["Redirect user"]
```

## Registration And OTP Workflow

```mermaid
sequenceDiagram
    participant User
    participant Flask
    participant DB
    participant Email

    User->>Flask: Submit registration form
    Flask->>DB: Check email uniqueness
    Flask->>DB: Create unverified user
    Flask->>DB: Store hashed OTP
    Flask->>Email: Send OTP email
    Flask-->>User: Open OTP page

    User->>Flask: Submit OTP
    Flask->>DB: Verify active OTP
    Flask->>DB: Mark OTP used
    Flask->>DB: Mark user verified
    Flask->>DB: Create session
    Flask-->>User: Redirect after verification
```

## Password Reset Workflow

```mermaid
flowchart TD
    Forgot["User opens forgot password"] --> EmailInput["Submit email"]
    EmailInput --> UserCheck{"User exists?"}
    UserCheck -- No --> Error["Show account error"]
    UserCheck -- Yes --> OTP["Generate and store hashed OTP"]
    OTP --> Send["Send OTP email"]
    Send --> Verify["User enters OTP"]
    Verify --> Valid{"OTP valid?"}
    Valid -- No --> Retry["Show retry message"]
    Valid -- Yes --> Reset["Allow password reset"]
    Reset --> NewPass["Submit new password"]
    NewPass --> Hash["Hash password"]
    Hash --> Update["Update user password"]
    Update --> Login["Create new session"]
```

## Chatbot Lead Booking Workflow

```mermaid
sequenceDiagram
    participant User
    participant Chatbot
    participant Flask
    participant Zoom
    participant MongoDB
    participant Email

    User->>Chatbot: Start booking flow
    Chatbot->>Chatbot: Collect service, budget, timeline, contact, and call type
    Chatbot->>Flask: Submit booking request

    alt Video call selected
        Flask->>Zoom: Create meeting
        Zoom-->>Flask: Return join link
    end

    Flask->>MongoDB: Save booking
    Flask->>Email: Send booking notification
    Flask-->>Chatbot: Return confirmation
    Chatbot-->>User: Show booking confirmation
```

## Admin Scheduling Workflow

```mermaid
flowchart TD
    Admin["Admin opens leads and bookings"] --> Pick["Select booking and schedule time"]
    Pick --> Submit["Submit schedule update"]
    Submit --> API["Scheduling endpoint"]
    API --> Fetch["Fetch booking"]
    Fetch --> Video{"Video call?"}
    Video -- Yes --> Zoom["Create Zoom meeting"]
    Video -- No --> SkipZoom["Continue without meeting link"]
    Zoom --> UpdateDB["Update booking status and schedule"]
    SkipZoom --> UpdateDB
    UpdateDB --> Notify["Send confirmation email"]
    Notify --> UI["Dashboard reflects update"]
```

## Redis Workflow

```mermaid
flowchart LR
    App["Flask App"] --> R["Redis"]
    R --> Sessions["Cached Sessions"]
    R --> Limits["Rate Limit Data"]
    Admin["Admin Dashboard"] --> R
    Admin --> View["View Cache Status"]
    Admin --> Manage["Manage Cache Entries"]
```

## Docker Deployment Architecture

```mermaid
flowchart TD
    Compose["docker-compose.yml"] --> Web["AIAS web container"]
    Compose --> Redis["Redis container"]

    Web --> Gunicorn["Gunicorn"]
    Gunicorn --> Flask["Flask App"]
    Flask --> MongoDB["MongoDB Atlas"]
    Flask --> Redis
    Flask --> SMTP["Gmail SMTP"]
    Flask --> Zoom["Zoom API"]

    Redis --> Volume["Redis data volume"]
```

## Docker Services

| Service | Purpose |
| --- | --- |
| `aias-platform` | Runs the Flask application through Gunicorn |
| `aias-redis` | Runs Redis for cache and rate-limit support |

The Docker setup builds the web app from `Dockerfile`, exposes port `5000`, uses environment values from `.env`, runs Redis with persistence, and includes container health checks.

## Environment Setup

Create a local `.env` from `.env.example`:

```powershell
copy .env.example .env
```

Fill in the required local values for Flask, MongoDB, Redis, SMTP, Google OAuth, Zoom, and admin configuration.

The real `.env` file must remain local and must not be committed.

## Run Locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Run With Docker

```powershell
docker compose up --build
```

Open:

```text
http://127.0.0.1:5000
```

## Deployment Commands

### Option 1: Docker Compose (Recommended)

Build and start:

```bash
docker compose up --build -d
```

Check status:

```bash
docker compose ps
```

View logs:

```bash
docker compose logs --tail=120 aias-web
docker compose logs --tail=120 aias-redis
```

Stop stack:

```bash
docker compose down
```

### Option 2: Standalone Docker CLI (Without Compose)

If you wish to deploy the containers manually using the `docker` CLI instead of `docker-compose`, use one of the following setups:

#### Setup A: Using a Shared Network (Recommended)
1. Create the bridge network:
   ```bash
   docker network create aias-network
   ```
2. Start the Redis container (named `aias-redis`):
   ```bash
   docker run -d --name aias-redis --network aias-network redis:7-alpine
   ```
3. Start the Web App container (named `aias-platform`):
   ```bash
   docker run -d --name aias-platform --network aias-network -p 5000:5000 --env-file .env -e REDIS_URL=redis://aias-redis:6379/0 aias-aias-web:latest
   ```

#### Setup B: Using Host Port Mapping
1. Start the Redis container:
   ```bash
   docker run -d --name aias-redis -p 6379:6379 redis:7-alpine
   ```
2. Start the Web App container pointing to your host's Redis loopback:
   ```bash
   docker run -d --name aias-platform -p 5000:5000 --env-file .env -e REDIS_URL=redis://host.docker.internal:6379/0 aias-aias-web:latest
   ```

---

## Smoke Test Checklist

```text
[ ] docker compose config --quiet
[ ] docker compose up --build -d
[ ] web container is healthy
[ ] redis container is healthy
[ ] / returns 200
[ ] /signin returns 200
[ ] /register returns 200
[ ] /forgot-password returns 200
[ ] Redis connectivity works from the web container
[ ] MongoDB connectivity works from the web container
[ ] No critical errors appear in container logs
```

## Useful Validation Commands

```bash
python -m compileall -q .
docker compose config --quiet
docker compose exec -T aias-platform python -m compileall -q .
docker compose exec -T aias-platform python -c "from app import create_app; app=create_app(); print(len(app.url_map._rules))"
```

## Production Notes

- **Live Azure Deployment:** `https://aias-web-standard.bluedune-52554353.southeastasia.azurecontainerapps.io/`
- **Reverse Proxy Header Support:** The Flask app includes `werkzeug.middleware.proxy_fix.ProxyFix` to correctly handle `X-Forwarded-Proto`, `X-Forwarded-Host`, and `X-Forwarded-For` from Azure Container Apps ingress.
- **Google OAuth Redirect URI in Production:**
  Add the following URI to your Google Cloud Console's *Authorized Redirect URIs*:
  ```text
  https://aias-web-standard.bluedune-52554353.southeastasia.azurecontainerapps.io/auth/google/callback
  ```
- Use production-grade secret storage for deployed credentials.
- Rotate credentials before first public deployment.
- Keep `.env` local and out of version control.
- Use HTTPS through a reverse proxy or platform load balancer.
- Keep Docker, Python dependencies, and system packages updated.
- Monitor application logs, container health, Redis health, and database connectivity.

## Documentation

For the complete internal project overview, see:

```text
information.md
```
