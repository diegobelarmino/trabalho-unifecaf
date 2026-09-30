import os

from dotenv import load_dotenv

from app import preparar

load_dotenv()

app = preparar()

if __name__ == "__main__":
    porta = int(os.getenv("FLASK_PORT", "5000"))
    host = os.getenv("BIND_HOST", "127.0.0.1")
    debug = os.getenv("FLASK_ENV", "development") != "production"
    app.run(host=host, port=porta, debug=debug)
