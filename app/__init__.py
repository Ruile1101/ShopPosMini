import os
import sys

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from config import Config

db = SQLAlchemy()


def get_resource_template_and_static_paths():
    """Return the application template and static directories for source and frozen runs.

    PyInstaller collects the packaged template and static folders into top-level
    directories named templates/static inside the one-file extraction root. In
    the source tree those assets remain under app/templates and app/static.
    """
    if getattr(sys, 'frozen', False):
        resource_root = sys._MEIPASS
        return (
            os.path.join(resource_root, 'templates'),
            os.path.join(resource_root, 'static')
        )

    resource_root = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )

    return (
        os.path.join(resource_root, 'app', 'templates'),
        os.path.join(resource_root, 'app', 'static')
    )


def create_app():
    template_dir, static_dir = get_resource_template_and_static_paths()

    app = Flask(
        __name__,
        template_folder=template_dir,
        static_folder=static_dir
    )

    app.config.from_object(Config)

    db.init_app(app)

    # Vercel's deployed filesystem is read-only. Schema creation and the
    # compatibility ALTER statements remain available for local development,
    # but must be run against the external database before deploying.
    if not os.getenv('VERCEL'):
        with app.app_context():
            from app import models  # noqa: F401

            db.create_all()

            try:
                dialect = db.engine.dialect.name

                inspector = inspect(db.engine)

                # ---------------------------------------------------------
                # SALE TABLE
                # ---------------------------------------------------------
                sale_columns = []

                if 'sale' in inspector.get_table_names():
                    sale_columns = [
                        column['name']
                        for column in inspector.get_columns('sale')
                    ]

                # Keep legacy sale tables compatible with the newer
                # document-aware workflow.
                if 'document_type' not in sale_columns:
                    if dialect == 'sqlite':
                        db.session.execute(
                            text(
                                "ALTER TABLE sale "
                                "ADD COLUMN document_type "
                                "VARCHAR(20) NOT NULL DEFAULT 'receipt'"
                            )
                        )

                    elif dialect == 'postgresql':
                        db.session.execute(
                            text(
                                "ALTER TABLE sale "
                                "ADD COLUMN IF NOT EXISTS document_type "
                                "VARCHAR(20) NOT NULL DEFAULT 'receipt'"
                            )
                        )

                if 'discount' not in sale_columns:
                    if dialect == 'sqlite':
                        db.session.execute(
                            text(
                                "ALTER TABLE sale "
                                "ADD COLUMN discount "
                                "FLOAT NOT NULL DEFAULT 0.00"
                            )
                        )

                    elif dialect == 'postgresql':
                        db.session.execute(
                            text(
                                "ALTER TABLE sale "
                                "ADD COLUMN IF NOT EXISTS discount "
                                "FLOAT NOT NULL DEFAULT 0.00"
                            )
                        )

                if 'deposit' not in sale_columns:
                    if dialect == 'sqlite':
                        db.session.execute(
                            text(
                                "ALTER TABLE sale "
                                "ADD COLUMN deposit "
                                "FLOAT NOT NULL DEFAULT 0.00"
                            )
                        )

                    elif dialect == 'postgresql':
                        db.session.execute(
                            text(
                                "ALTER TABLE sale "
                                "ADD COLUMN IF NOT EXISTS deposit "
                                "FLOAT NOT NULL DEFAULT 0.00"
                            )
                        )

                # ---------------------------------------------------------
                # SALE ITEM TABLE
                # ---------------------------------------------------------
                if 'sale_item' in inspector.get_table_names():

                    sale_item_columns = [
                        column['name']
                        for column in inspector.get_columns('sale_item')
                    ]

                    # Add the new unit column to older databases.
                    #
                    # Existing sale items will automatically use PC.
                    #
                    # Supported values from the sales form include:
                    # PC, BOX, PACK, SET, UNIT, BOOK
                    if 'unit' not in sale_item_columns:
                        if dialect == 'sqlite':
                            db.session.execute(
                                text(
                                    "ALTER TABLE sale_item "
                                    "ADD COLUMN unit "
                                    "VARCHAR(20) NOT NULL DEFAULT 'PC'"
                                )
                            )

                        elif dialect == 'postgresql':
                            db.session.execute(
                                text(
                                    "ALTER TABLE sale_item "
                                    "ADD COLUMN IF NOT EXISTS unit "
                                    "VARCHAR(20) NOT NULL DEFAULT 'PC'"
                                )
                            )

                    # A sale-item description is entered through a textarea
                    # and may contain multiple lines. PostgreSQL enforces
                    # VARCHAR(255), so widen databases created by older
                    # versions of the app.
                    if dialect == 'postgresql':
                        description_column = next(
                            (
                                column
                                for column in inspector.get_columns(
                                    'sale_item'
                                )
                                if column['name'] == 'description'
                            ),
                            None,
                        )

                        if (
                            description_column
                            and getattr(
                                description_column['type'],
                                'length',
                                None
                            )
                        ):
                            db.session.execute(
                                text(
                                    "ALTER TABLE sale_item "
                                    "ALTER COLUMN description TYPE TEXT"
                                )
                            )

                db.session.commit()

            except Exception:
                # Keep the app booting for environments where the sales table
                # is not yet present.
                db.session.rollback()

    from app.routes import main
    app.register_blueprint(main)

    return app