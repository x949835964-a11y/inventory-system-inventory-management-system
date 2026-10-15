"""Entry point: `flask run` in development, WSGI target in production."""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
