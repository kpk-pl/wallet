import pytest
import tests
from flaskr import create_app


@pytest.fixture
def client():
    app = create_app({"TESTING": True,
                      "MONGO_HOST": tests.MONGO_TEST_HOST,
                      "MONGO_PORT": str(tests.MONGO_TEST_PORT),
                      "MONGO_SESSIONS": False,
                      })

    with app.test_client() as client:
        yield client
