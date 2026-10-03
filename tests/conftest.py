import os
import tempfile

# Must be set before `app` is imported (module-level app uses ACEEST_DB).
os.environ.setdefault("ACEEST_DB", os.path.join(tempfile.mkdtemp(), "import_time.db"))

import pytest  # noqa: E402

from app import create_app  # noqa: E402


@pytest.fixture
def client(tmp_path):
    flask_app = create_app(str(tmp_path / "test.db"))
    flask_app.config["TESTING"] = True
    return flask_app.test_client()


@pytest.fixture
def asha(client):
    """A saved client with height/weight on a fat-loss program."""
    r = client.post("/clients", json={"name": "Asha", "age": 28, "height": 165,
                                      "weight": 70, "program": "Fat Loss (FL) - 3 day",
                                      "target_weight": 62, "target_adherence": 85})
    assert r.status_code == 201
    return client
