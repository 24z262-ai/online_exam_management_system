import os


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "exam_user")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "exam_password")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "online_exam_db")
    APP_TIMEZONE = os.getenv("APP_TIMEZONE", "Asia/Kolkata")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

