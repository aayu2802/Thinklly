"""
Configuration for Single Database Multi-Tenant School Management System
"""

import os
from urllib.parse import quote_plus
import dotenv
dotenv.load_dotenv()  # Load environment variables from .env file

class Config:
    """Base configuration for single database multi-tenancy"""

    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'supersecretkey'

    # Database settings (prefer local .env, fall back to old defaults only if unset)
    MYSQL_HOST = os.environ.get('DB_HOST', 'localhost')
    MYSQL_PORT = int(os.environ.get('DB_PORT', 3306))
    MYSQL_USERNAME = os.environ.get('DB_USER', 'lxyscuzf_eduedusaintsaint')
    # NOTE: do NOT override an explicitly empty password from .env
    MYSQL_PASSWORD = os.environ.get('DB_PASS') if 'DB_PASS' in os.environ else 'eG@9vK7-4D=V9cM1'
    MYSQL_DATABASE = os.environ.get('DB_NAME', 'lxyscuzf_schoolerp')
    MYSQL_CHARSET = 'utf8mb4'

    # SQLAlchemy settings
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 280,
        'pool_pre_ping': True,
    }

    def _encoded_password(self) -> str:
        """Percent-encode special characters for URL usage."""
        return quote_plus(self.MYSQL_PASSWORD) if self.MYSQL_PASSWORD else ''

    def get_database_uri(self) -> str:
        """Get single database URI for all tenants."""
        user = self.MYSQL_USERNAME
        pwd = self._encoded_password()
        host = self.MYSQL_HOST
        port = self.MYSQL_PORT
        database = self.MYSQL_DATABASE
        
        if pwd:
            return f"mysql+pymysql://{user}:{pwd}@{host}:{port}/{database}?charset={self.MYSQL_CHARSET}"
        return f"mysql+pymysql://{user}@{host}:{port}/{database}?charset={self.MYSQL_CHARSET}"

    def get_mysql_root_uri(self) -> str:
        """Get root URI (no database) for CREATE/DROP DATABASE ops."""
        user = self.MYSQL_USERNAME
        pwd = self._encoded_password()
        host = self.MYSQL_HOST
        port = self.MYSQL_PORT
        
        if pwd:
            return f"mysql+pymysql://{user}:{pwd}@{host}:{port}?charset={self.MYSQL_CHARSET}"
        return f"mysql+pymysql://{user}@{host}:{port}?charset={self.MYSQL_CHARSET}"


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    # Use in-memory SQLite for testing
    def get_database_uri(self) -> str:
        return 'sqlite:///:memory:'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
