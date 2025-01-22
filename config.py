import os
from datetime import timedelta


class Config:
    # Base configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    # File upload settings
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static/uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

    # Database settings (using shelve)
    SHELVE_DIR = os.path.join(BASE_DIR, 'data')

    # Session settings
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # Security settings
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False
    # Add any production-specific settings here


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SHELVE_DIR = os.path.join(Config.BASE_DIR, 'test_data')


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}