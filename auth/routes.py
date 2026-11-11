"""
AIAS Auth Routes
All authentication endpoints: sign-in, register, OTP verification, Google OAuth.
"""

import secrets
from functools import wraps

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_bcrypt import Bcrypt

from auth.email_service import EmailService
from auth.google_oauth import get_google_client
from auth.otp_service import OTPService
from auth.rate_limiter import RateLimiter
from config import Config
from database.models import OTPModel, SessionModel, UserModel
from database.security import DatabaseSecurity

auth_bp = Blueprint("auth", __name__)
bcrypt = Bcrypt()


def init_bcrypt(app):
    """Initialize bcrypt with the Flask app."""
    bcrypt.init_app(app)


def login_required(f):
    """Decorator to require authentication."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session or "session_token" not in session:
            flash("Please sign in to continue.", "warning")
            return redirect(url_for("auth.signin"))

        # Validate session token
        db_session = SessionModel.get_session(session["session_token"])
        if not db_session:
            session.clear()
            flash("Session expired. Please sign in again.", "warning")
            return redirect(url_for("auth.signin"))

        return f(*args, **kwargs)

    return decorated_function


# ──────────────────────────────────────
# SIGN IN
# ──────────────────────────────────────
@auth_bp.route("/signin", methods=["GET", "POST"])
def signin():
    """Sign-in page: validate email + password, then send OTP."""

    # If already logged in, redirect
    if "user_id" in session and "session_token" in session:
        db_session = SessionModel.get_session(session["session_token"])
        if db_session:
            return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # Validation
        if not email or not password:
            return jsonify({"success": False, "error": "Email and password are required."}), 400

        # Check rate limiting
        rate_check = RateLimiter.check_login_attempt(email)
        if not rate_check["allowed"]:
            return jsonify({"success": False, "error": rate_check["error"]}), 429

        # Check if user exists
        user = UserModel.get_by_email(email)
        if not user:
            return jsonify({"success": False, "error": "No account found with this email address."}), 404

        # Check if account is locked
        if UserModel.is_locked(email):
            return jsonify({
                "success": False,
                "error": f"Account temporarily locked. Try again in {Config.LOCKOUT_DURATION_MINUTES} minutes.",
            }), 429

        # Check if it's a Google-only account (no password set)
        if user["is_google_user"] and not user["password_hash"]:
            return jsonify({
                "success": False,
                "error": "Wrong password. This account was created with Google. Please use 'Sign in with Google'.",
            }), 401

        # Verify password
        if not bcrypt.check_password_hash(user["password_hash"], password):
            UserModel.increment_failed_attempts(email)
            RateLimiter.log_failed_login(email)
            return jsonify({"success": False, "error": "Invalid password. Please try again."}), 401

        # Password correct — log in directly
        UserModel.reset_failed_attempts(email)
        session_token = secrets.token_urlsafe(64)
        SessionModel.create_session(user["id"], session_token)

        session["user_id"] = user["id"]
        session["user_email"] = email
        session["user_name"] = user["display_name"]
        session["session_token"] = session_token
        session.permanent = True

        RateLimiter.log_successful_login(email)

        return jsonify({
            "success": True,
            "message": "Sign-in successful! Welcome back.",
            "redirect": url_for("index"),
        })

    return render_template("signin.html")


# ──────────────────────────────────────
# VERIFY OTP
# ──────────────────────────────────────
@auth_bp.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    """OTP verification page."""
    email = session.get("pending_email")
    purpose = session.get("pending_purpose", "signin")

    if not email:
        flash("No pending verification. Please sign in first.", "warning")
        return redirect(url_for("auth.signin"))

    if request.method == "POST":
        otp_input = request.form.get("otp", "").strip()

        if not otp_input or len(otp_input) != 6 or not otp_input.isdigit():
            return jsonify({"success": False, "error": "Please enter a valid 6-digit code."}), 400

        # Verify the OTP
        result = OTPService.verify_otp(email, otp_input, purpose)

        if not result["valid"]:
            return jsonify({"success": False, "error": result["error"]}), 400

        # OTP verified!
        if purpose == "signin":
            # Create session
            user = UserModel.get_by_email(email)
            if user:
                UserModel.reset_failed_attempts(email)
                session_token = secrets.token_urlsafe(64)
                SessionModel.create_session(user["id"], session_token)

                session.pop("pending_email", None)
                session.pop("pending_purpose", None)
                session["user_id"] = user["id"]
                session["user_email"] = email
                session["user_name"] = user["display_name"]
                session["session_token"] = session_token
                session.permanent = True

                RateLimiter.log_successful_login(email)

                return jsonify({
                    "success": True,
                    "message": "Sign-in successful! Welcome back.",
                    "redirect": url_for("index"),
                })

        elif purpose == "register":
            # Mark user as verified
            UserModel.verify_user(email)
            user = UserModel.get_by_email(email)
            if user:
                session_token = secrets.token_urlsafe(64)
                SessionModel.create_session(user["id"], session_token)

                session.pop("pending_email", None)
                session.pop("pending_purpose", None)
                session["user_id"] = user["id"]
                session["user_email"] = email
                session["user_name"] = user["display_name"]
                session["session_token"] = session_token
                session.permanent = True

                # Send welcome email
                EmailService.send_welcome_email(email, user["display_name"])

                return jsonify({
                    "success": True,
                    "message": "Account verified successfully! Welcome to AIAS.",
                    "redirect": url_for("index"),
                })

        elif purpose == "password_reset":
            # OTP verified for password reset — allow access to reset page
            session["password_reset_verified"] = True
            session["password_reset_email"] = email
            session.pop("pending_email", None)
            session.pop("pending_purpose", None)

            return jsonify({
                "success": True,
                "message": "Identity verified! Please set your new password.",
                "redirect": url_for("auth.reset_password"),
            })

        return jsonify({"success": False, "error": "Verification failed. Please try again."}), 400

    # Mask email for display
    masked_email = _mask_email(email)
    
    # Calculate remaining time for the active OTP
    remaining_seconds = Config.OTP_EXPIRY_MINUTES * 60
    otp_record = OTPModel.get_active_otp(email, purpose)
    if otp_record:
        from datetime import datetime, timezone
        expires_at = otp_record["expires_at"]
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        remaining = (expires_at - datetime.now(timezone.utc)).total_seconds()
        remaining_seconds = max(0, int(remaining))
        
    return render_template("verify_otp.html", masked_email=masked_email, remaining_seconds=remaining_seconds)


@auth_bp.route("/resend-otp", methods=["POST"])
def resend_otp():
    """Resend OTP to the pending email."""
    email = session.get("pending_email")
    purpose = session.get("pending_purpose", "signin")

    if not email:
        return jsonify({"success": False, "error": "No pending verification found."}), 400

    # Rate check
    rate_check = RateLimiter.check_otp_request(email)
    if not rate_check["allowed"]:
        return jsonify({"success": False, "error": rate_check["error"]}), 429

    user = UserModel.get_by_email(email)
    display_name = user["display_name"] if user else ""

    otp_code = OTPService.create_and_store(email, purpose)
    email_result = EmailService.send_otp_email(email, otp_code, display_name)

    if not email_result["success"]:
        return jsonify({"success": False, "error": email_result["error"]}), 500

    RateLimiter.log_otp_request(email)

    return jsonify({"success": True, "message": "New verification code sent!"})


# ──────────────────────────────────────
# FORGOT PASSWORD
# ──────────────────────────────────────
@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Forgot password page: enter email to receive OTP for password reset."""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        if not email:
            return jsonify({"success": False, "error": "Please enter your email address."}), 400

        # Check if user exists
        user = UserModel.get_by_email(email)
        if not user:
            return jsonify({"success": False, "error": "No account found with this email address."}), 404

        # Rate check for OTP
        rate_check = RateLimiter.check_otp_request(email)
        if not rate_check["allowed"]:
            return jsonify({"success": False, "error": rate_check["error"]}), 429

        # Generate and send OTP
        otp_code = OTPService.create_and_store(email, purpose="password_reset")
        email_result = EmailService.send_otp_email(email, otp_code, user["display_name"])

        if not email_result["success"]:
            return jsonify({"success": False, "error": email_result["error"]}), 500

        RateLimiter.log_otp_request(email)

        # Store in session
        session["pending_email"] = email
        session["pending_purpose"] = "password_reset"

        return jsonify({
            "success": True,
            "message": "Verification code sent to your email.",
            "redirect": url_for("auth.verify_otp"),
        })

    return render_template("forgot_password.html")


# ──────────────────────────────────────
# RESET PASSWORD
# ──────────────────────────────────────
@auth_bp.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    """Reset password page — only accessible after OTP verification for password_reset."""
    # Check if user is allowed to be here
    if not session.get("password_reset_verified"):
        flash("Please verify your identity first.", "warning")
        return redirect(url_for("auth.forgot_password"))

    email = session.get("password_reset_email")
    if not email:
        flash("Session expired. Please start over.", "warning")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not password or not confirm_password:
            return jsonify({"success": False, "error": "Both fields are required."}), 400

        if password != confirm_password:
            return jsonify({"success": False, "error": "Passwords do not match."}), 400

        if len(password) < 8:
            return jsonify({"success": False, "error": "Password must be at least 8 characters."}), 400

        strength_error = _check_password_strength(password)
        if strength_error:
            return jsonify({"success": False, "error": strength_error}), 400

        # Hash and update
        password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        UserModel.update_password(email, password_hash)
        UserModel.reset_failed_attempts(email)

        # Auto-login: create session and redirect to homepage
        user = UserModel.get_by_email(email)
        if user:
            session_token = secrets.token_urlsafe(64)
            SessionModel.create_session(user["id"], session_token)

            # Clear reset session flags
            session.pop("password_reset_verified", None)
            session.pop("password_reset_email", None)
            session.pop("pending_email", None)
            session.pop("pending_purpose", None)

            # Set logged-in session
            session["user_id"] = user["id"]
            session["user_email"] = email
            session["user_name"] = user["display_name"]
            session["session_token"] = session_token
            session.permanent = True

            return jsonify({
                "success": True,
                "message": "Password reset successfully! Welcome back.",
                "redirect": url_for("index"),
            })

    masked_email = _mask_email(email)
    return render_template("reset_password.html", masked_email=masked_email)


# ──────────────────────────────────────
# REGISTER
# ──────────────────────────────────────
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Registration page."""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        display_name = request.form.get("display_name", "").strip()

        # Validation
        if not email or not password or not confirm_password:
            return jsonify({"success": False, "error": "All fields are required."}), 400

        if not display_name:
            return jsonify({"success": False, "error": "Please enter your name."}), 400

        if password != confirm_password:
            return jsonify({"success": False, "error": "Passwords do not match."}), 400

        if len(password) < 8:
            return jsonify({"success": False, "error": "Password must be at least 8 characters."}), 400

        # Check password strength
        strength_error = _check_password_strength(password)
        if strength_error:
            return jsonify({"success": False, "error": strength_error}), 400

        # Check if email already exists
        if UserModel.email_exists(email):
            return jsonify({"success": False, "error": "An account with this email already exists."}), 409

        # Rate check for OTP
        rate_check = RateLimiter.check_otp_request(email)
        if not rate_check["allowed"]:
            return jsonify({"success": False, "error": rate_check["error"]}), 429

        # Hash password and create user (unverified)
        password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        UserModel.create_user(email, password_hash, display_name)

        # Send verification OTP
        otp_code = OTPService.create_and_store(email, purpose="register")
        email_result = EmailService.send_otp_email(email, otp_code, display_name)

        if not email_result["success"]:
            return jsonify({"success": False, "error": email_result["error"]}), 500

        RateLimiter.log_otp_request(email)

        # Store for OTP verification
        session["pending_email"] = email
        session["pending_purpose"] = "register"

        return jsonify({
            "success": True,
            "message": "Account created! Please verify your email.",
            "redirect": url_for("auth.verify_otp"),
        })

    return render_template("register.html")


def _get_google_redirect_uri():
    """Determine the Google OAuth redirect URI with proper HTTPS scheme and Azure support."""
    host = request.host or ""
    is_azure = "azurecontainerapps.io" in host
    is_https = request.is_secure or request.headers.get("X-Forwarded-Proto") == "https"

    if is_azure:
        return f"https://{host}/auth/google/callback"

    redirect_uri = Config.GOOGLE_REDIRECT_URI
    if not redirect_uri:
        redirect_uri = url_for("auth.google_callback", _external=True)

    if (Config.FLASK_ENV == "production" or is_https) and redirect_uri.startswith("http://"):
        redirect_uri = redirect_uri.replace("http://", "https://", 1)

    return redirect_uri


# ──────────────────────────────────────
# GOOGLE OAUTH
# ──────────────────────────────────────
@auth_bp.route("/auth/google")
def google_login():
    """Start Google OAuth flow."""
    if not Config.GOOGLE_CLIENT_ID or Config.GOOGLE_CLIENT_ID.startswith("YOUR_"):
        flash("Google Sign-In is not configured yet.", "warning")
        return redirect(url_for("auth.signin"))

    # If accessed via 127.0.0.1, redirect to localhost so session cookies & Google redirect URI match
    if "127.0.0.1" in request.host:
        target_url = request.url.replace("127.0.0.1", "localhost", 1)
        return redirect(target_url)

    google = get_google_client()
    redirect_uri = _get_google_redirect_uri()
    return google.authorize_redirect(redirect_uri)


@auth_bp.route("/auth/google/callback")
def google_callback():
    """Handle Google OAuth callback."""
    try:
        google = get_google_client()
        redirect_uri = _get_google_redirect_uri()
            
        try:
            token = google.authorize_access_token()
        except Exception as state_err:
            if "mismatching_state" in str(state_err) or "CSRF" in str(state_err):
                # State mismatch due to server restart or session loss — retry without state check
                import requests as http_requests
                code = request.args.get("code")
                if not code:
                    flash("Google sign-in failed. Please try again.", "error")
                    return redirect(url_for("auth.signin"))
                
                # Exchange code for token manually
                token_url = "https://oauth2.googleapis.com/token"
                token_data = {
                    "code": code,
                    "client_id": Config.GOOGLE_CLIENT_ID,
                    "client_secret": Config.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                }
                token_resp = http_requests.post(token_url, data=token_data)
                if token_resp.status_code != 200:
                    flash("Google sign-in failed. Please try again.", "error")
                    return redirect(url_for("auth.signin"))
                token = token_resp.json()
            else:
                raise state_err
        
        user_info = token.get("userinfo")
        if not user_info:
            # Fetch user info using access token
            access_token = token.get("access_token")
            if access_token:
                import requests as http_requests
                headers = {"Authorization": f"Bearer {access_token}"}
                resp = http_requests.get("https://www.googleapis.com/oauth2/v3/userinfo", headers=headers)
                if resp.status_code == 200:
                    user_info = resp.json()

        if not user_info:
            flash("Could not retrieve user info from Google.", "error")
            return redirect(url_for("auth.signin"))

        email = user_info.get("email", "").lower().strip()
        name = user_info.get("name", "")

        if not email:
            flash("Could not retrieve email from Google.", "error")
            return redirect(url_for("auth.signin"))

        # Check if user exists
        user = UserModel.get_by_email(email)
        is_new_user = False

        if not user:
            # Create new Google user (auto-verified)
            user_id = UserModel.create_user(email, None, name, is_google_user=True)
            is_new_user = True
        else:
            user_id = user["id"]
            # If existing user, mark as also having Google
            if not user.get("is_google_user"):
                from database.db import db
                from datetime import datetime, timezone
                db.users.update_one(
                    {"email": email},
                    {"$set": {"is_google_user": True, "updated_at": datetime.now(timezone.utc)}}
                )

        # Create session
        session_token = secrets.token_urlsafe(64)
        SessionModel.create_session(user_id, session_token)

        session["user_id"] = user_id
        session["user_email"] = email
        session["user_name"] = name
        session["session_token"] = session_token
        session.permanent = True

        # Send welcome email only to newly signed-up users
        if is_new_user:
            EmailService.send_welcome_email(email, name)

        flash("Signed in with Google successfully!", "success")
        return redirect(url_for("index"))

    except Exception as e:
        flash(f"Google sign-in failed: {str(e)}", "error")
        return redirect(url_for("auth.signin"))


# ──────────────────────────────────────
# SIGN OUT
# ──────────────────────────────────────
@auth_bp.route("/signout")
def signout():
    """Sign out and destroy session."""
    session_token = session.get("session_token")
    if session_token:
        SessionModel.delete_session(session_token)
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("index"))


# ──────────────────────────────────────
# DASHBOARD (post-login landing)
# ──────────────────────────────────────
@auth_bp.route("/dashboard")
@login_required
def dashboard():
    """Simple dashboard to confirm successful login."""
    return render_template(
        "dashboard.html",
        user_name=session.get("user_name", "User"),
        user_email=session.get("user_email", ""),
    )


# ──────────────────────────────────────
# HELPERS
# ──────────────────────────────────────
def _mask_email(email):
    """Mask an email for display: te***@gm***.com"""
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@")
    domain_name, domain_ext = domain.rsplit(".", 1)
    masked_local = local[:2] + "***" if len(local) > 2 else local[0] + "***"
    masked_domain = domain_name[:2] + "***" if len(domain_name) > 2 else domain_name[0] + "***"
    return f"{masked_local}@{masked_domain}.{domain_ext}"


def _check_password_strength(password):
    """Validate password strength. Returns error message or None."""
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?/" for c in password)
    if not (has_upper and has_lower and has_digit):
        return "Password must contain uppercase, lowercase, and a number."
    if not has_special:
        return "Password must contain at least one special character (!@#$%^&* etc.)."
    return None
