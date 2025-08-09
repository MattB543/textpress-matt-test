from app.main import app
from fastapi.testclient import TestClient


def main() -> None:
    c = TestClient(app)
    r = c.get("/healthz")
    print("/healthz:", r.status_code, r.json())


if __name__ == "__main__":
    main()


