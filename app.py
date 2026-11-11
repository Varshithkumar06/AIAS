"""
AIAS — Main Flask Application
Entry point for the Sign-In & Verification System.
"""

import logging
import os
import sys
import secrets
from datetime import datetime, timedelta, timezone

from flask import Flask, redirect, render_template, request, jsonify, session as flask_session, url_for, send_from_directory
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config
from auth.routes import auth_bp, init_bcrypt
from auth.google_oauth import init_google_oauth
from database.db import db_manager, db, sanitize_doc
from database.security import DatabaseSecurity


def start_local_redis():
    """Attempt to start the local Redis server if not already running (Windows or Linux/Docker)."""
    import socket
    import subprocess
    import shutil
    import time
    
    # Check if port 6379 is in use
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.4)
            if s.connect_ex(('127.0.0.1', 6379)) == 0:
                return  # Redis is already running
    except Exception:
        pass

    # Windows bundled Redis
    redis_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Redis", "redis-server.exe")
    if os.path.exists(redis_path):
        try:
            creationflags = 0x08000000 if sys.platform == "win32" else 0
            subprocess.Popen([redis_path], creationflags=creationflags, cwd=os.path.dirname(redis_path))
            time.sleep(0.8)
            return
        except Exception as e:
            print(f"[Startup] Failed to start bundled Redis: {e}")

    # Linux / Container system redis-server
    redis_bin = shutil.which("redis-server")
    if redis_bin:
        try:
            subprocess.Popen([redis_bin, "--daemonize", "yes", "--dir", "/tmp", "--protected-mode", "no"])
            time.sleep(0.5)
            return
        except Exception as e:
            print(f"[Startup] Failed to auto-start system Redis: {e}")


def create_app():
    """Application factory."""
    app = Flask(__name__)

    # Support reverse proxies (Azure Container Apps, Nginx, etc.)
    # Reads X-Forwarded-For, X-Forwarded-Proto, X-Forwarded-Host, X-Forwarded-Prefix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # ── Configuration ──
    app.config["SECRET_KEY"] = Config.SECRET_KEY
    app.config["BASE_URL"] = Config.BASE_URL
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=Config.SESSION_LIFETIME_HOURS)
    app.config["SESSION_COOKIE_HTTPONLY"] = Config.SESSION_COOKIE_HTTPONLY
    app.config["SESSION_COOKIE_SAMESITE"] = Config.SESSION_COOKIE_SAMESITE
    app.config["SESSION_COOKIE_SECURE"] = Config.SESSION_COOKIE_SECURE
    app.config["WTF_CSRF_TIME_LIMIT"] = 3600  # 1 hour CSRF token validity

    # ── Security: CSRF Protection ──
    csrf = CSRFProtect(app)

    # ── Global Context Processor ──
    @app.context_processor
    def inject_global_urls():
        return {
            "BASE_URL": Config.BASE_URL,
            "APP_URL": Config.BASE_URL,
        }

    # ── Initialize Extensions ──
    init_bcrypt(app)

    # ── Google OAuth (only if configured) ──
    if Config.GOOGLE_CLIENT_ID and not Config.GOOGLE_CLIENT_ID.startswith("YOUR_"):
        init_google_oauth(app)

    # ── Structured Logging ──
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    log = logging.getLogger("aias.app")

    # ── Startup Connection Verification ──
    log.info("[Startup] Verifying database connectivity...")
    try:
        db_health = db_manager.health_check()
        if db_health["status"] == "healthy":
            log.info(
                "[Startup] ✓ Database HEALTHY — %s | Latency: %.0fms",
                db_health["connection_type"], db_health["latency_ms"]
            )
        else:
            log.warning("[Startup] ✗ Database UNHEALTHY — %s", db_health.get("error", "unknown"))
    except Exception as exc:
        log.warning("[Startup] ✗ Database check failed: %s", str(exc)[:200])

    # Auto-start Redis if configured for localhost and not running
    if "localhost" in Config.REDIS_URL or "127.0.0.1" in Config.REDIS_URL:
        start_local_redis()

    log.info("[Startup] Verifying Redis connectivity...")
    try:
        from auth.redis_service import RedisService
        redis_health = RedisService.health_check()
        if redis_health["status"] == "healthy":
            log.info(
                "[Startup] ✓ Redis HEALTHY — %s | Latency: %.0fms | v%s",
                redis_health["connection_type"],
                redis_health["latency_ms"],
                redis_health.get("redis_version", "?"),
            )
        else:
            log.warning(
                "[Startup] ✗ Redis %s — %s (app will function without Redis)",
                redis_health["status"].upper(), redis_health.get("error", "")
            )
    except Exception as exc:
        log.warning("[Startup] ✗ Redis check failed: %s (app will function without Redis)", str(exc)[:200])

    # ── Register Blueprints ──
    app.register_blueprint(auth_bp)

    # ── Health Check Endpoint ──
    @app.route("/health")
    @csrf.exempt
    def health_check():
        """Reports connectivity status of MongoDB and Redis with connection types and latencies."""
        db_status = db_manager.health_check()
        try:
            from auth.redis_service import RedisService
            redis_status = RedisService.health_check()
        except Exception as exc:
            redis_status = {"service": "Redis", "status": "error", "error": str(exc)[:200]}

        overall = "healthy"
        if db_status["status"] != "healthy":
            overall = "unhealthy"
        elif redis_status["status"] != "healthy":
            overall = "degraded"  # App works without Redis, just slower

        return jsonify({
            "status": overall,
            "services": {
                "database": db_status,
                "redis": redis_status,
            }
        })

    # ── Root Route: Serve Homepage ──
    @app.route("/")
    def index():
        return render_template(
            "homepage.html",
            logged_in="user_id" in flask_session,
            user_name=flask_session.get("user_name", ""),
            user_email=flask_session.get("user_email", ""),
        )

    # ── Asset Files Route ──
    @app.route("/asset/<path:filename>")
    def serve_asset(filename):
        return send_from_directory(os.path.join(app.root_path, "asset"), filename)

    # ── Admin Dashboard ──
    ADMIN_EMAILS = {"aiasprivateltd@gmail.com", "varshithkumar815@gmail.com"}

    @app.route("/admin")
    def admin_dashboard():
        """Admin dashboard — only accessible to admin emails."""
        # Check if logged in
        if "user_id" not in flask_session:
            return redirect(url_for("auth.signin"))

        # Check if admin
        user_email = flask_session.get("user_email", "").lower().strip()
        if user_email not in ADMIN_EMAILS:
            return redirect(url_for("index"))

        # Fetch all data from database
        try:
            users = list(db.users.find().sort("created_at", -1))
            users = [sanitize_doc(u) for u in users]

            bookings = list(db.bookings.find().sort("created_at", -1))
            bookings = [sanitize_doc(b) for b in bookings]

            now = datetime.now(timezone.utc)
            sessions_data = list(db.sessions.find({"expires_at": {"$gt": now}}))
            sessions_data = [sanitize_doc(s) for s in sessions_data]

            otps = list(db.otp_codes.find())
            otps = [sanitize_doc(o) for o in otps]

            rate_logs = list(db.rate_limit_log.find().sort("created_at", -1).limit(100))
            rate_logs = [sanitize_doc(r) for r in rate_logs]
        except Exception as exc:
            print(f"[Admin Dashboard DB Error] {str(exc)}")
            users, bookings, sessions_data, otps, rate_logs = [], [], [], [], []

        # Compute stats
        total_users = len(users)
        verified_users = sum(1 for u in users if u.get("is_verified"))
        google_users = sum(1 for u in users if u.get("is_google_user"))
        total_bookings = len(bookings)
        booked_count = sum(1 for b in bookings if b.get("lead_status") == "booked")
        new_count = sum(1 for b in bookings if b.get("lead_status") == "new")
        active_sessions = len(sessions_data)
        total_otps = len(otps)
        bookings_with_problems = [b for b in bookings if b.get("problem_statement") and b.get("problem_statement").strip()]

        return render_template(
            "admin.html",
            admin_email=user_email,
            users=users,
            bookings=bookings,
            bookings_with_problems=bookings_with_problems,
            rate_logs=rate_logs,
            total_users=total_users,
            verified_users=verified_users,
            google_users=google_users,
            total_bookings=total_bookings,
            booked_count=booked_count,
            new_count=new_count,
            active_sessions=active_sessions,
            total_otps=total_otps,
        )

    # ── Admin Query Executor ──
    @app.route("/admin/query", methods=["POST"])
    def admin_query():
        """Execute a custom MongoDB query (admin only)."""
        if "user_id" not in flask_session:
            return jsonify({"success": False, "error": "Unauthorized: Not signed in"}), 401

        user_email = flask_session.get("user_email", "").lower().strip()
        if user_email not in ADMIN_EMAILS:
            return jsonify({"success": False, "error": "Forbidden: Admin access required"}), 403

        try:
            data = request.get_json(force=True) or {}
            query = data.get("query", "").strip()
        except Exception:
            return jsonify({"success": False, "error": "Invalid request payload"}), 400

        if not query:
            return jsonify({"success": False, "error": "Query cannot be empty"}), 400

        try:
            from database.db import db_manager
            from bson import ObjectId
            from datetime import datetime as dt
            
            res = db_manager.execute_eval(query)
            
            # Form return payload
            if isinstance(res, list):
                # Extrapolate columns from all dictionaries in the list
                columns_set = set()
                for item in res:
                    if isinstance(item, dict):
                        columns_set.update(item.keys())
                columns = sorted(list(columns_set))
                # Ensure '_id' is first if present
                if '_id' in columns:
                    columns.remove('_id')
                    columns.insert(0, '_id')
                if 'id' in columns:
                    columns.remove('id')
                    columns.insert(1, 'id')
                
                serialized_rows = []
                for item in res:
                    if isinstance(item, dict):
                        serialized_row = {}
                        for col_name in columns:
                            val = item.get(col_name)
                            if isinstance(val, dt):
                                serialized_row[col_name] = val.strftime('%Y-%m-%d %H:%M:%S')
                            elif isinstance(val, ObjectId):
                                serialized_row[col_name] = str(val)
                            elif isinstance(val, bytes):
                                serialized_row[col_name] = val.hex()
                            else:
                                serialized_row[col_name] = val
                        serialized_rows.append(serialized_row)
                    else:
                        serialized_rows.append({"value": str(item)})
                        columns = ["value"]
                        
                return jsonify({
                    "success": True,
                    "type": "select",
                    "columns": columns,
                    "rows": serialized_rows,
                    "row_count": len(serialized_rows)
                })
            else:
                message = f"Query executed successfully. Result: {res}"
                # Handle pymongo collection execution results
                if hasattr(res, "modified_count"):
                    message = f"Query executed. Modified count: {res.modified_count}"
                elif hasattr(res, "deleted_count"):
                    message = f"Query executed. Deleted count: {res.deleted_count}"
                elif hasattr(res, "inserted_id"):
                    message = f"Query executed. Inserted ID: {res.inserted_id}"
                
                return jsonify({
                    "success": True,
                    "type": "dml",
                    "row_count": 1 if res else 0,
                    "message": message
                })
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e)
            }), 400

    # ── Admin Redis Status & Keys Inspector ──
    @app.route("/admin/redis-status", methods=["GET"])
    def admin_redis_status():
        """Get current Redis connection status, server info, and key listings (admin only)."""
        if "user_id" not in flask_session:
            return jsonify({"success": False, "error": "Unauthorized: Not signed in"}), 401

        user_email = flask_session.get("user_email", "").lower().strip()
        if user_email not in ADMIN_EMAILS:
            return jsonify({"success": False, "error": "Forbidden: Admin access required"}), 403

        from auth.redis_service import RedisService
        # Circuit breaker handles recovery automatically — no manual reset needed
        client = RedisService.get_client()
        if not client:
            redis_health = RedisService.health_check()
            return jsonify({
                "success": True,
                "connected": False,
                "circuit_state": redis_health.get("circuit_state", "UNKNOWN"),
                "error": redis_health.get("error", "Redis server is disconnected or offline.")
            })

        try:
            # Server Info
            info = client.info()
            server_info = {
                "version": info.get("redis_version", "Unknown"),
                "memory_used": info.get("used_memory_human", "Unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "uptime_days": info.get("uptime_in_days", 0),
                "uptime_seconds": info.get("uptime_in_seconds", 0)
            }

            # Retrieve all keys
            keys = client.keys("*")
            keys_list = []
            for k in keys:
                try:
                    k_type = client.type(k)
                    ttl = client.ttl(k)
                except Exception:
                    k_type = "string"
                    ttl = -1
                
                # Fetch preview of value for simple string keys
                val_preview = "—"
                try:
                    if k_type == "string":
                        val_str = client.get(k)
                        if val_str:
                            if len(val_str) > 80:
                                val_preview = val_str[:80] + "..."
                            else:
                                val_preview = val_str
                    elif k_type == "zset":
                        val_preview = f"Sorted Set ({client.zcard(k)} members)"
                    elif k_type == "set":
                        val_preview = f"Set ({client.scard(k)} members)"
                    elif k_type == "hash":
                        val_preview = f"Hash ({client.hlen(k)} fields)"
                    elif k_type == "list":
                        val_preview = f"List ({client.llen(k)} items)"
                except Exception as e:
                    val_preview = f"Error reading value: {str(e)}"
                
                keys_list.append({
                    "key": k,
                    "type": k_type,
                    "ttl": ttl,
                    "value": val_preview
                })

            # Sort keys alphabetically
            keys_list.sort(key=lambda x: x["key"])

            return jsonify({
                "success": True,
                "connected": True,
                "server_info": server_info,
                "keys": keys_list
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "error": f"Error querying Redis: {str(e)}"
            }), 500

    # ── Admin Redis Action Handler ──
    @app.route("/admin/redis-action", methods=["POST"])
    def admin_redis_action():
        """Perform administrative actions on Redis cache like deleting keys or flushing cache (admin only)."""
        if "user_id" not in flask_session:
            return jsonify({"success": False, "error": "Unauthorized: Not signed in"}), 401

        user_email = flask_session.get("user_email", "").lower().strip()
        if user_email not in ADMIN_EMAILS:
            return jsonify({"success": False, "error": "Forbidden: Admin access required"}), 403

        from auth.redis_service import RedisService
        client = RedisService.get_client()
        if not client:
            return jsonify({"success": False, "error": "Redis is not connected or offline."}), 400

        try:
            data = request.get_json(force=True) or {}
            action = data.get("action")
            key = data.get("key")
        except Exception:
            return jsonify({"success": False, "error": "Invalid request payload"}), 400

        if action == "delete":
            if not key:
                return jsonify({"success": False, "error": "Key parameter required for deletion"}), 400
            try:
                deleted = client.delete(key)
                if deleted:
                    return jsonify({"success": True, "message": f"Key '{key}' deleted successfully."})
                else:
                    return jsonify({"success": False, "error": f"Key '{key}' not found."}), 404
            except Exception as e:
                return jsonify({"success": False, "error": f"Failed to delete key: {str(e)}"}), 500

        elif action == "flush":
            try:
                client.flushdb()
                return jsonify({"success": True, "message": "Redis database flushed successfully."})
            except Exception as e:
                return jsonify({"success": False, "error": f"Failed to flush Redis: {str(e)}"}), 500

        else:
            return jsonify({"success": False, "error": f"Invalid action: {action}"}), 400

    # ── Book-a-Call Endpoint (exempt from CSRF — called via chatbot fetch) ──
    @app.route("/book-call", methods=["POST"])
    @csrf.exempt
    def book_call():
        """Receive lead data from chatbot, save to DB, generate Zoom meeting if needed, and send email notification."""
        zoom_meeting_link = ""
        scheduled_at = None
        try:
            data = request.get_json(force=True) or {}
            name              = data.get("name", "N/A")
            email             = data.get("email", "N/A")
            whatsapp          = data.get("whatsapp", "")
            service_needed    = data.get("service_needed", "N/A")
            budget_range      = data.get("budget_range", "N/A")
            timeline          = data.get("timeline", "N/A")
            problem_statement = data.get("problem_statement", "")
            source            = data.get("source", "website")
            lead_status       = data.get("lead_status", "new")
            call_type         = data.get("call_type", "Voice Call")
            ts                = data.get("timestamp", "N/A")

            if call_type == "Video Conference":
                try:
                    from auth.zoom_service import ZoomService
                    zoom_meeting_link = ZoomService.create_meeting() or ""
                    if zoom_meeting_link:
                        scheduled_at = datetime.utcnow() + timedelta(hours=72)
                except Exception:
                    zoom_meeting_link = ""

            # Save to database
            try:
                db.bookings.insert_one({
                    "name": name,
                    "email": email,
                    "whatsapp": whatsapp,
                    "service_needed": service_needed,
                    "budget_range": budget_range,
                    "timeline": timeline,
                    "problem_statement": problem_statement,
                    "source": source,
                    "lead_status": lead_status,
                    "call_type": call_type,
                    "zoom_meeting_link": zoom_meeting_link,
                    "scheduled_at": scheduled_at,
                    "created_at": datetime.now(timezone.utc)
                })
            except Exception as e:
                print(f"[book_call DB Warning] {str(e)}")

            # Send email notification to team and client in a background thread
            try:
                import threading
                from auth.email_service import EmailService
                threading.Thread(
                    target=EmailService.send_booking_notification,
                    kwargs={
                        "name": name,
                        "email": email,
                        "whatsapp": whatsapp,
                        "service_needed": service_needed,
                        "budget_range": budget_range,
                        "timeline": timeline,
                        "problem_statement": problem_statement,
                        "call_type": call_type,
                        "zoom_meeting_link": zoom_meeting_link,
                        "timestamp": ts,
                        "scheduled_at": scheduled_at
                    },
                    daemon=True
                ).start()
            except Exception as e:
                print(f"[book_call Email Thread Warning] {str(e)}")

        except Exception:
            pass  # Never fail the frontend
        return jsonify({
            "success": True,
            "zoom_meeting_link": zoom_meeting_link,
            "scheduled_at": scheduled_at.isoformat() if scheduled_at else None
        })

    # ── Admin Schedule Meeting Endpoint ──
    @app.route("/admin/schedule-meeting", methods=["POST"])
    def admin_schedule_meeting():
        """Schedule or reschedule a Zoom meeting or Voice call from the Admin Console."""
        if "user_id" not in flask_session:
            return jsonify({"success": False, "error": "Unauthorized: Not signed in"}), 401

        user_email = flask_session.get("user_email", "").lower().strip()
        if user_email not in ADMIN_EMAILS:
            return jsonify({"success": False, "error": "Forbidden: Admin access required"}), 403

        try:
            data = request.get_json(force=True) or {}
            booking_id = data.get("booking_id")
            scheduled_at_str = data.get("scheduled_at") # Local time string e.g. "2026-05-27T14:30"
        except Exception:
            return jsonify({"success": False, "error": "Invalid request payload"}), 400

        if not booking_id or not scheduled_at_str:
            return jsonify({"success": False, "error": "Missing booking_id or scheduled_at parameter"}), 400

        # Parse local ISO string
        try:
            scheduled_at_dt = datetime.fromisoformat(scheduled_at_str)
        except Exception as e:
            return jsonify({"success": False, "error": f"Invalid date-time format: {str(e)}"}), 400

        # Fetch booking details from database
        try:
            from database.models import to_object_id
            doc = db.bookings.find_one({"_id": to_object_id(booking_id)})
            booking = sanitize_doc(doc)
        except Exception as e:
            return jsonify({"success": False, "error": f"Database read error: {str(e)}"}), 500

        if not booking:
            return jsonify({"success": False, "error": "Booking not found"}), 404

        call_type = booking.get("call_type") or "Voice Call"
        zoom_meeting_link = booking.get("zoom_meeting_link") or ""

        # Schedule Zoom meeting if Video Conference
        if call_type == "Video Conference":
            try:
                from auth.zoom_service import ZoomService
                # Use Asia/Kolkata timezone since the dashboard and clients are local
                zoom_meeting_link = ZoomService.create_meeting(start_time_dt=scheduled_at_dt, timezone="Asia/Kolkata") or ""
            except Exception as e:
                print(f"[Admin Schedule Zoom Warning] {str(e)}")
                # We will continue even if Zoom API fails, so we can save the scheduled date/time.

        # Update database
        try:
            from database.models import to_object_id
            db.bookings.update_one(
                {"_id": to_object_id(booking_id)},
                {
                    "$set": {
                        "zoom_meeting_link": zoom_meeting_link,
                        "scheduled_at": scheduled_at_dt,
                        "lead_status": "booked"
                    }
                }
            )
        except Exception as e:
            return jsonify({"success": False, "error": f"Failed to update booking in database: {str(e)}"}), 500

        # Send email confirmation in a background thread to prevent blocking
        try:
            import threading
            from auth.email_service import EmailService
            threading.Thread(
                target=EmailService.send_booking_notification,
                kwargs={
                    "name": booking.get("name", "Client"),
                    "email": booking.get("email", ""),
                    "whatsapp": booking.get("whatsapp", ""),
                    "service_needed": booking.get("service_needed", "N/A"),
                    "budget_range": booking.get("budget_range", "N/A"),
                    "timeline": booking.get("timeline", "N/A"),
                    "problem_statement": booking.get("problem_statement", ""),
                    "call_type": call_type,
                    "zoom_meeting_link": zoom_meeting_link,
                    "timestamp": datetime.utcnow().isoformat(),
                    "scheduled_at": scheduled_at_dt
                },
                daemon=True
            ).start()
        except Exception as e:
            print(f"[Admin Schedule Email Thread Warning] {str(e)}")

        return jsonify({
            "success": True,
            "zoom_meeting_link": zoom_meeting_link,
            "scheduled_at": scheduled_at_dt.isoformat(),
            "message": "Meeting successfully scheduled and email sent to client."
        })

    # ── Client Rate Limiting & Periodic Cleanup ──
    @app.before_request
    def before_request():
        # Exclude static assets and media from rate limiting
        if request.endpoint in ('static', 'serve_asset') or request.path.startswith('/static/') or request.path.startswith('/asset/'):
            return

        # Resolve real client IP
        ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        if ip and "," in ip:
            ip = ip.split(",")[0].strip()

        # Redis rate limit check to protect from DOS attacks
        try:
            from auth.redis_service import RedisService
            rate_limit_key = f"ratelimit:ip:{ip}"
            allowed, current_count = RedisService.check_rate_limit(
                rate_limit_key,
                Config.GLOBAL_RATE_LIMIT_LIMIT,
                Config.GLOBAL_RATE_LIMIT_WINDOW
            )
            if not allowed:
                return jsonify({"error": "Too many requests. Please try again later."}), 429
        except Exception as e:
            print(f"[RateLimit Warning] {str(e)}")

        # Run cleanup roughly every 100th request (probabilistic)
        if secrets.randbelow(100) == 0:
            try:
                DatabaseSecurity.cleanup_all()
            except Exception:
                pass  # Don't break requests on cleanup failure

    # ── Error Handlers ──
    @app.errorhandler(404)
    def not_found(e):
        return redirect(url_for("auth.signin"))

    @app.errorhandler(500)
    def server_error(e):
        original_exc = getattr(e, "original_exception", None)
        exc_str = str(original_exc or e)
        
        if request.is_json or request.headers.get("Accept") == "application/json" or request.path in ["/signin", "/register", "/book-call"]:
            return jsonify({"success": False, "error": f"Internal Server Error: {exc_str}"}), 500
        return f"<div style='font-family:sans-serif;padding:2rem;max-width:600px;margin:auto;'><h2>Internal Server Error</h2><p>{exc_str}</p></div>", 500

    return app


if __name__ == "__main__":
    if Config.FLASK_ENV == "development":
        start_local_redis()
        
    app = create_app()
    port = int(os.getenv("PORT", 5000))
    print("\n" + "=" * 56)
    print("  [AIAS] Platform")
    print(f"  -> Local:      http://localhost:{port}/")
    print(f"  -> Sign In:    http://localhost:{port}/signin")
    print(f"  -> Register:   http://localhost:{port}/register")
    print(f"  -> Azure Live: {Config.BASE_URL}/")
    print("=" * 56 + "\n")
    app.run(
        host="0.0.0.0",
        port=port,
        debug=(Config.FLASK_ENV == "development"),
        use_reloader=False,
    )
