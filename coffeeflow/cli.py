import re
import sqlite3
import click
from werkzeug.security import generate_password_hash
from .db import init_db, transaction


def register_cli(app):
    @app.cli.command('init-db')
    def init_command():
        """Створити відсутні таблиці, не видаляючи дані."""
        init_db()
        click.echo('Database schema ready.')

    @app.cli.command('create-admin')
    @click.option('--username', prompt=True)
    @click.password_option(confirmation_prompt=True)
    def create_admin(username, password):
        """Створити адміністратора; пароль вводиться приховано."""
        username = username.strip().lower()
        if not re.fullmatch(r'[a-z0-9_.-]{3,40}', username):
            raise click.ClickException('Username: 3–40 lowercase ASCII letters, digits, _, . or -.')
        if not 12 <= len(password) <= 128:
            raise click.ClickException('Password must contain 12–128 characters.')
        try:
            with transaction() as db:
                db.execute('INSERT INTO admins(username,password_hash) VALUES (?,?)',
                           (username, generate_password_hash(password)))
        except sqlite3.IntegrityError:
            raise click.ClickException('Username already exists.') from None
        click.echo('Administrator created.')

    @app.cli.command('seed-demo')
    def seed_demo():
        """Додати навчальне меню тільки до порожнього каталогу."""
        with transaction() as db:
            if db.execute('SELECT 1 FROM categories LIMIT 1').fetchone():
                raise click.ClickException('Catalog is not empty; existing data kept.')
            coffee = db.execute('INSERT INTO categories(name) VALUES (?)', ('Кава',)).lastrowid
            desserts = db.execute('INSERT INTO categories(name) VALUES (?)', ('Десерти',)).lastrowid
            db.executemany('INSERT INTO products(category_id,name,description,price_cents) VALUES (?,?,?,?)', [
                (coffee, 'Еспресо', 'Класична чорна кава, 30 мл', 4500),
                (coffee, 'Капучино', 'Кава з молоком, 250 мл', 6500),
                (desserts, 'Чизкейк', 'Порція сирного десерту', 11000)])
        click.echo('Demo menu created (no default administrator).')
