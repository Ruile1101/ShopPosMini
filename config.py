import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE_URL = os.getenv('DATABASE_URL')

# Vercel Functions have a read-only application filesystem. A bundled SQLite
# file can be read, but sales and other changes cannot be persisted, so require
# an external database explicitly for a Vercel deployment.
if os.getenv('VERCEL') and not DATABASE_URL:
    raise RuntimeError(
        'DATABASE_URL must be set for Vercel. SQLite files are not writable or '
        'persistent in Vercel Functions.'
    )

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'replace-this-secret-key-in-production')
    SQLALCHEMY_DATABASE_URI = DATABASE_URL or 'sqlite:///' + os.path.join(BASE_DIR, 'pos.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    FLASK_RUN_HOST = os.getenv('FLASK_RUN_HOST', '0.0.0.0')
    FLASK_RUN_PORT = int(os.getenv('FLASK_RUN_PORT', '5000'))
