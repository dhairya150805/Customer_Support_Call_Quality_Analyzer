from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import QueuePool
import os, socket, dns.resolver
from dotenv import load_dotenv
from urllib.parse import urlparse, urlunparse

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# ---------------------------------------------------------------------------
# Workaround: if the system DNS cannot resolve the DB host, fall back to
# Google Public DNS (8.8.8.8) and replace the hostname with a resolved IP.
# ---------------------------------------------------------------------------
_raw_db_url = os.getenv("DATABASE_URL", "")

def _resolve_db_url(url: str) -> str:
    """Replace hostname with IP if system DNS fails, using Google DNS."""
    if not url:
        return url
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return url
    try:
        socket.getaddrinfo(host, None)
        return url                       # system DNS works, use as-is
    except socket.gaierror:
        pass
    # Resolve via Google Public DNS
    try:
        resolver = dns.resolver.Resolver(configure=False)
        resolver.nameservers = ["8.8.8.8", "8.8.4.4"]
        answers = resolver.resolve(host, "A")
        ip = str(answers[0])
        # Rebuild netloc  (user:password@ip:port)
        netloc = parsed.netloc.replace(host, ip)
        new_url = urlunparse(parsed._replace(netloc=netloc))
        print(f"[database] System DNS failed for {host}; resolved via Google DNS → {ip}")
        return new_url
    except Exception as e:
        print(f"[database] Google DNS fallback also failed: {e}")
        return url

DATABASE_URL = _resolve_db_url(_raw_db_url)
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set in .env")

engine = create_engine(
    DATABASE_URL,
    echo=False,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
