# AIAS System Architecture & Flow Diagrams

This document contains Mermaid diagrams illustrating the system architecture, authentication flows, chatbot lead qualification, Zoom integration, and Docker deployment topology for the AIAS platform.

---

## 1. High-Level System Architecture

```mermaid
graph TD
    Client[Browser / Client] -->|HTTP / HTTPS| Gunicorn[Gunicorn Web Server]
    Gunicorn --> Flask[Flask Web Application]
    
    subgraph Flask App Blueprint & Services
        Flask --> Auth[Auth Blueprint / Route Handlers]
        Flask --> Admin[Admin Blueprint / Console]
        Flask --> Chatbot[Aria Chatbot / Lead Engine]
        
        Auth --> OTP[OTP Service - SHA256]
        Auth --> RateLimiter[Rate Limiter - Redis / MongoDB]
        Auth --> Email[Email Service - Gmail SMTP]
        Auth --> OAuth[Google OAuth - Authlib]
        
        Chatbot --> Zoom[Zoom Service - Server-to-Server OAuth]
        Chatbot --> Email
    end

    subgraph External Integrations
        Email -->|SMTP| Gmail[Gmail Server]
        OAuth -->|OAuth2| Google[Google Identity Provider]
        Zoom -->|REST API| ZoomAPI[Zoom Cloud Platform]
    end

    subgraph Data & Storage Layer
        Flask -->|PyMongo| Mongo[(MongoDB Atlas)]
        Flask -->|redis-py| Redis[(Redis Container)]
    end
```

---

## 2. User Registration & OTP Verification Flow

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Browser
    participant Flask as Flask App
    participant Redis as Redis Cache
    participant Mongo as MongoDB Atlas
    participant SMTP as Gmail SMTP

    User->>Browser: Fill Registration Form (Name, Email, Password)
    Browser->>Flask: POST /register
    Flask->>Redis: Check Rate Limit for Email
    alt Rate Limit Exceeded
        Redis-->>Flask: Limit Reached
        Flask-->>Browser: 429 Too Many Requests
    else Limit OK
        Flask->>Mongo: Check Existing User Email
        alt Email Exists
            Mongo-->>Flask: User Record Found
            Flask-->>Browser: Email Already Registered Error
        else Email Available
            Flask->>Flask: Generate 6-digit OTP & Hash (SHA256)
            Flask->>Mongo: Store Unverified User & Hashed OTP
            Flask->>SMTP: Send OTP Email
            SMTP-->>User: Delivers Verification Email with OTP
            Flask-->>Browser: Redirect to /verify-otp
        end
    end

    User->>Browser: Enters 6-digit OTP
    Browser->>Flask: POST /verify-otp
    Flask->>Mongo: Fetch User OTP Record
    Flask->>Flask: Hash Input OTP & Compare
    alt OTP Match & Not Expired
        Flask->>Mongo: Mark User as Verified & Set Active
        Flask->>Flask: Establish Session Cookie
        Flask-->>Browser: Redirect to /dashboard
    else Invalid / Expired OTP
        Flask->>Mongo: Increment Failed Attempts
        Flask-->>Browser: Show OTP Invalid Error
    end
```

---

## 3. Google OAuth 2.0 Sign-In Flow

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Browser
    participant Flask as Flask App
    participant Google as Google OAuth Server
    participant Mongo as MongoDB Atlas

    User->>Browser: Click "Sign in with Google"
    Browser->>Flask: GET /auth/google
    Flask->>Google: Redirect to Google Authorization Endpoint
    Google-->>User: Prompt Consent Screen
    User->>Google: Approve Permissions
    Google-->>Browser: Redirect to /auth/google/callback with Auth Code
    Browser->>Flask: GET /auth/google/callback?code=...
    Flask->>Google: Exchange Auth Code for Access Token & User Info
    Google-->>Flask: Return User Profile (email, name, sub)
    Flask->>Mongo: Lookup or Create User Record (is_google_user=True)
    Flask->>Flask: Create Session Cookie
    Flask-->>Browser: Redirect to /dashboard
```

---

## 4. Aria Chatbot Lead Qualification & Zoom Meeting Booking

```mermaid
sequenceDiagram
    autonumber
    actor Prospect as Web Prospect
    participant Chatbot as Aria Chatbot UI
    participant Flask as Flask /book-call
    participant Zoom as Zoom Service
    participant Mongo as MongoDB Atlas
    participant Email as Email Service

    Prospect->>Chatbot: Interacts with Aria Chatbot
    Chatbot->>Prospect: Asks Qualification Questions (Role, Company, Budget)
    Prospect->>Chatbot: Selects Preferred Date & Time for Demo Call
    Chatbot->>Flask: POST /book-call (Lead Info + Selected Slot)
    
    Flask->>Zoom: Get Server-to-Server OAuth Access Token
    Zoom-->>Flask: Access Token Returned
    Flask->>Zoom: Create Meeting Endpoint (POST /users/me/meetings)
    Zoom-->>Flask: Meeting Link & Meeting ID Generated
    
    Flask->>Mongo: Save Lead & Booking Details (Status: Confirmed)
    Flask->>Email: Send Confirmation Email to Client
    Flask->>Email: Send Notification Email to Internal Sales Team
    Email-->>Prospect: Email with Calendar Invite & Zoom Link
    Flask-->>Chatbot: Return Success & Zoom Link
    Chatbot-->>Prospect: Display Booking Confirmation Card
```

---

## 5. Admin Dashboard & Operations Architecture

```mermaid
graph LR
    AdminUser[Admin User] -->|Session Cookie| AdminRoutes[Flask Admin Routes /admin]

    subgraph Admin Modules
        AdminRoutes --> UserMgmt[User Management]
        AdminRoutes --> LeadMgmt[Lead & Booking Console]
        AdminRoutes --> QueryConsole[MongoDB Raw Query Console]
        AdminRoutes --> RedisConsole[Redis Inspector & Flushing]
        AdminRoutes --> Scheduler[Meeting Rescheduler]
    end

    subgraph Storage Backends
        UserMgmt -->|CRUD| UsersColl[(MongoDB: users)]
        LeadMgmt -->|CRUD| LeadsColl[(MongoDB: leads)]
        QueryConsole -->|PyMongo Exec| MongoDb[(MongoDB Atlas)]
        RedisConsole -->|redis-py| RedisDb[(Redis Instance)]
        Scheduler -->|API| ZoomApi[Zoom REST API]
    end
```

---

## 6. Docker Deployment & Container Topology

```mermaid
graph TD
    Internet((Internet / Traffic)) -->|Port 80 / 443| Nginx[Reverse Proxy / Nginx]
    
    subgraph Docker Compose Network: aias-network
        Nginx -->|Port 8000| WebContainer[Container: aias-web]
        
        subgraph aias-web Container
            GunicornProc[Gunicorn Process Manager]
            Workers[Gunicorn Worker 1..N]
            GunicornProc --> Workers
            Workers --> FlaskApp[AIAS Flask Application]
        end
        
        FlaskApp -->|Port 6379| RedisContainer[Container: aias-redis]
        
        subgraph aias-redis Container
            RedisServer[Redis Server Alpine]
            VolData[Persistent Volume: redis-data]
            RedisServer --- VolData
        end
    end

    subgraph Cloud Dependencies
        FlaskApp -->|TLS / Port 27017| MongoAtlas[MongoDB Atlas Cluster]
        FlaskApp -->|TLS / Port 465| GmailSmtp[Gmail SMTP Server]
        FlaskApp -->|HTTPS| ZoomCloud[Zoom Cloud Services]
    end
```
