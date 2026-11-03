from app import create_app


def test_home_shows_landing_page_to_anonymous_users():
    app = create_app({"TESTING": True, "SECRET_KEY": "test"})
    response = app.test_client().get("/")
    assert response.status_code == 200
    assert b"Your learning space is ready." in response.data


def test_login_page_is_available():
    app = create_app({"TESTING": True, "SECRET_KEY": "test"})
    response = app.test_client().get("/login")
    assert response.status_code == 200
    assert b"Sign in to your workspace" in response.data