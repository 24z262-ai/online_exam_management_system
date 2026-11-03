from contextlib import contextmanager

from flask import current_app, g


def get_db():
    if "db" not in g:
        import mysql.connector

        g.db = mysql.connector.connect(
            host=current_app.config["MYSQL_HOST"],
            port=current_app.config["MYSQL_PORT"],
            user=current_app.config["MYSQL_USER"],
            password=current_app.config["MYSQL_PASSWORD"],
            database=current_app.config["MYSQL_DATABASE"],
            autocommit=False,
        )
    return g.db


def close_db(_error=None):
    connection = g.pop("db", None)
    if connection is not None and connection.is_connected():
        connection.close()


@contextmanager
def cursor(dictionary=False):
    connection = get_db()
    db_cursor = connection.cursor(dictionary=dictionary)
    try:
        yield db_cursor
    except Exception:
        connection.rollback()
        raise
    finally:
        db_cursor.close()


def init_db():
    """Apply the checked-in schema to the configured MySQL database."""
    with current_app.open_resource("database/schema.sql") as schema_file:
        statements = [part.strip() for part in schema_file.read().decode("utf-8").split(";") if part.strip()]
    with cursor() as db_cursor:
        for statement in statements:
            db_cursor.execute(statement)
        # Existing Docker volumes keep their original schema. Add the scheduling
        # fields in place so upgrades do not require deleting the database volume.
        db_cursor.execute(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='exams'"
        )
        existing_columns = {row[0] for row in db_cursor.fetchall()}
        migrations = {
            "starts_at": "ALTER TABLE exams ADD COLUMN starts_at DATETIME NULL",
            "ends_at": "ALTER TABLE exams ADD COLUMN ends_at DATETIME NULL",
            "is_published": "ALTER TABLE exams ADD COLUMN is_published TINYINT(1) NOT NULL DEFAULT 0",
        }
        for column, statement in migrations.items():
            if column not in existing_columns:
                db_cursor.execute(statement)
        db_cursor.execute(
            "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='results'"
        )
        result_columns = {row[0] for row in db_cursor.fetchall()}
        if "is_published" not in result_columns:
            db_cursor.execute("ALTER TABLE results ADD COLUMN is_published TINYINT(1) NOT NULL DEFAULT 0")
    get_db().commit()

