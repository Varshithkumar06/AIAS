import logging
import threading
import time
from datetime import datetime, timezone
import pymongo
from bson import ObjectId

from config import Config

# Logger
logger = logging.getLogger("aias.database")

# ── Fix for dnspython / WSL DNS search label > 63 chars issue ──
try:
    import dns.resolver
    import dns.name

    _orig_read_resolv_conf = dns.resolver.Resolver.read_resolv_conf

    def _safe_read_resolv_conf(self, f):
        try:
            _orig_read_resolv_conf(self, f)
        except (dns.name.LabelTooLong, Exception) as err:
            logger.warning("[DB] Resolv.conf contained malformed search domain (%s). Using fallback DNS nameservers.", err)
            nameservers = []
            if isinstance(f, str):
                try:
                    with open(f, "r", encoding="utf-8") as fp:
                        lines = fp.readlines()
                except Exception:
                    lines = []
            elif hasattr(f, "seek"):
                try:
                    f.seek(0)
                    lines = f.readlines()
                except Exception:
                    lines = []
            else:
                lines = []

            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 2 and parts[0] == "nameserver":
                    nameservers.append(parts[1])

            if not nameservers:
                nameservers = ["8.8.8.8", "1.1.1.1"]

            self.nameservers = nameservers
            self.search = []

    dns.resolver.Resolver.read_resolv_conf = _safe_read_resolv_conf

    # Pre-initialize default_resolver safely so get_default_resolver never throws
    try:
        dns.resolver.get_default_resolver()
    except Exception:
        _clean_res = dns.resolver.Resolver(configure=False)
        _clean_res.nameservers = ["8.8.8.8", "1.1.1.1"]
        _clean_res.search = []
        dns.resolver.default_resolver = _clean_res
except ImportError:
    pass


def sanitize_doc(doc):
    """
    Sanitize a MongoDB document for the application.
    - Maps _id to string id to match the application's SQL expectation.
    - Ensures all naive datetimes are marked as UTC timezone-aware.
    """
    if doc is None:
        return None
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc["_id"])
    for k, v in doc.items():
        if isinstance(v, datetime) and v.tzinfo is None:
            doc[k] = v.replace(tzinfo=timezone.utc)
    return doc


class MongoDBManager:
    """
    Singleton manager for MongoDB connection pool, indexes, and health checks.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._client = None
        self._db = None
        self._indexes_setup_done = False
        self._indexes_setup_lock = threading.Lock()
        self._initialized = True

        # Initialize the connection pool
        self._connect()

    def _connect(self):
        """Establish client connection to MongoDB with pooling settings."""
        try:
            # Configure MongoClient with reliable defaults
            self._client = pymongo.MongoClient(
                Config.MONGO_URI,
                maxPoolSize=20,
                minPoolSize=2,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=5000,
                retryWrites=True,
            )
            # Access the database from the URI
            # pymongo.MongoClient(uri).get_default_database() automatically parses database name
            try:
                self._db = self._client.get_default_database()
            except Exception:
                # Fallback database if none specified in URI
                self._db = self._client["aias_db"]

            logger.info("[DB] MongoDB client initialized successfully.")
            self._verify_and_create_indexes()
        except Exception as exc:
            logger.critical("[DB] MongoDB client initialization failed: %s", str(exc))
            raise

    @property
    def db(self):
        """Get the database object directly."""
        if self._db is None:
            self._connect()
        return self._db

    def _verify_and_create_indexes(self):
        """Ensure all required database indexes are created thread-safely."""
        if self._indexes_setup_done:
            return

        with self._indexes_setup_lock:
            if self._indexes_setup_done:
                return

            try:
                db = self.db
                # 1. Users collection
                db.users.create_index("email", unique=True)
                
                # 2. OTP Codes collection
                db.otp_codes.create_index("email")
                db.otp_codes.create_index("expires_at")
                
                # 3. Sessions collection
                db.sessions.create_index("session_token", unique=True)
                db.sessions.create_index("user_id")
                
                # 4. Rate limit log collection
                db.rate_limit_log.create_index([("email", pymongo.ASCENDING), ("action", pymongo.ASCENDING)])
                db.rate_limit_log.create_index("created_at")

                # 5. Bookings collection
                db.bookings.create_index("email")
                db.bookings.create_index("created_at")

                self._indexes_setup_done = True
                logger.info("[DB] MongoDB indexes created/verified successfully.")
            except Exception as exc:
                logger.error("[DB] Failed to create/verify MongoDB indexes: %s", str(exc))
                # Do not re-raise; allow connection to continue since indexing can fail transiently

    def health_check(self):
        """
        Check database connectivity and return status report.
        """
        result = {
            "service": "MongoDB",
            "connection_type": "pymongo → SRV → TCP/TLS",
            "server": "ClusterAtlas",
            "database": self.db.name if self._db is not None else "unknown",
            "pooling": "pymongo connection pool",
            "status": "unhealthy",
            "latency_ms": None,
            "error": None,
        }
        try:
            t0 = time.monotonic()
            # Run ping command to verify connection
            self.db.command("ping")
            elapsed = (time.monotonic() - t0) * 1000
            result["status"] = "healthy"
            result["latency_ms"] = round(elapsed, 1)
        except Exception as exc:
            result["error"] = str(exc)[:300]
        return result

    def execute_eval(self, query_str):
        """
        Safely execute a MongoDB evaluation string from the Admin interface.
        Evaluates dynamic Python-like MongoDB queries using local scopes.
        """
        # Create safe evaluation scope with db object and utilities
        scope = {
            "db": self.db,
            "ObjectId": ObjectId,
            "datetime": datetime,
            "timezone": timezone,
            "pymongo": pymongo
        }

        # Check if the query is a simple command/eval
        try:
            # Evaluate expression
            res = eval(query_str, {"__builtins__": None}, scope)
            
            # If it's a cursor, convert to a list of dicts
            if isinstance(res, pymongo.cursor.Cursor):
                res = list(res)
            
            # Sanitize list or single dict
            if isinstance(res, list):
                res = [sanitize_doc(d) if isinstance(d, dict) else d for d in res]
            elif isinstance(res, dict):
                res = sanitize_doc(res)
                
            return res
        except Exception as exc:
            logger.error("[DB] Admin MongoDB eval failed: %s", str(exc))
            raise


# Global database manager and database instance
db_manager = MongoDBManager()
db = db_manager.db
