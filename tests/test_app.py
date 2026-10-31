import io
import os
import sys
from pathlib import Path

import pytest
from PIL import Image

# Добавляем корневую папку проекта в путь поиска Python
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import app as flask_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Создаёт тестовый клиент и временные папки для изображений."""

    upload_folder = tmp_path / "uploads"
    result_folder = tmp_path / "results"

    upload_folder.mkdir()
    result_folder.mkdir()

    monkeypatch.setattr(flask_app, "UPLOAD_FOLDER", str(upload_folder))
    monkeypatch.setattr(flask_app, "RESULT_FOLDER", str(result_folder))

    flask_app.app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret-key"
    )

    with flask_app.app.test_client() as test_client:
        yield test_client


def create_test_image():
    """Создаёт небольшое тестовое изображение PNG."""

    image = Image.new("RGB", (100, 100), color="white")
    image_bytes = io.BytesIO()
    image.save(image_bytes, format="PNG")
    image_bytes.seek(0)

    return image_bytes


def get_captcha_answer(client):
    """Получает пример CAPTCHA из сессии и возвращает ответ."""

    with client.session_transaction() as session:
        return session["captcha_answer"]


def test_main_page(client):
    """Проверяет открытие главной страницы."""

    response = client.get("/")

    assert response.status_code == 200
    assert "Обработка изображений".encode("utf-8") in response.data


def test_about_page(client):
    """Проверяет страницу О приложении."""

    response = client.get("/about")

    assert response.status_code == 200
    assert "Вариант 10".encode("utf-8") in response.data


def test_allowed_file():
    """Проверяет допустимые расширения файлов."""

    assert flask_app.allowed_file("photo.png")
    assert flask_app.allowed_file("photo.jpg")
    assert flask_app.allowed_file("photo.jpeg")

    assert not flask_app.allowed_file("document.txt")
    assert not flask_app.allowed_file("photo.gif")


def test_validate_image():
    """Проверяет корректное изображение."""

    image = create_test_image()

    assert flask_app.validate_image(image)


def test_invalid_image():
    """Проверяет отклонение некорректного файла."""

    invalid_file = io.BytesIO("Это не изображение".encode("utf-8"))

    assert not flask_app.validate_image(invalid_file)


def test_draw_vertical_cross(tmp_path):
    """Проверяет создание вертикальной линии."""

    source = tmp_path / "source.png"
    result = tmp_path / "result.png"

    image = Image.new("RGB", (100, 100), "white")
    image.save(source)

    flask_app.draw_cross(
        str(source),
        str(result),
        "#ff0000",
        5,
        "vertical"
    )

    assert result.exists()

    with Image.open(result) as processed:
        assert processed.getpixel((50, 50)) == (255, 0, 0)


def test_draw_horizontal_cross(tmp_path):
    """Проверяет создание горизонтальной линии."""

    source = tmp_path / "source.png"
    result = tmp_path / "result.png"

    image = Image.new("RGB", (100, 100), "white")
    image.save(source)

    flask_app.draw_cross(
        str(source),
        str(result),
        "#0000ff",
        5,
        "horizontal"
    )

    assert result.exists()

    with Image.open(result) as processed:
        assert processed.getpixel((50, 50)) == (0, 0, 255)


def test_create_histogram(tmp_path):
    """Проверяет создание гистограммы."""

    source = tmp_path / "source.png"
    histogram = tmp_path / "histogram.png"

    image = Image.new("RGB", (100, 100), "white")
    image.save(source)

    flask_app.create_histogram(
        str(source),
        str(histogram),
        "Тестовая гистограмма"
    )

    assert histogram.exists()
    assert os.path.getsize(histogram) > 0


def test_successful_upload(client):
    """Проверяет успешную обработку изображения."""

    response = client.get("/")
    assert response.status_code == 200

    captcha_answer = get_captcha_answer(client)

    response = client.post(
        "/",
        data={
            "image": (create_test_image(), "test.png"),
            "color": "#ff0000",
            "thickness": "5",
            "orientation": "vertical",
            "captcha_answer": str(captcha_answer)
        },
        content_type="multipart/form-data"
    )

    assert response.status_code == 200
    assert "Изображение успешно обработано!".encode("utf-8") in response.data
    assert "Гистограммы распределения цветов".encode("utf-8") in response.data


def test_wrong_captcha(client):
    """Проверяет отклонение неправильной CAPTCHA."""

    client.get("/")
    captcha_answer = get_captcha_answer(client)

    response = client.post(
        "/",
        data={
            "captcha_answer": str(captcha_answer + 1)
        }
    )

    assert response.status_code == 200
    assert "Неправильный ответ CAPTCHA!".encode("utf-8") in response.data


def test_invalid_file_extension(client):
    """Проверяет отклонение неподдерживаемого расширения."""

    client.get("/")
    captcha_answer = get_captcha_answer(client)

    response = client.post(
        "/",
        data={
            "image": (io.BytesIO(b"test"), "document.txt"),
            "captcha_answer": str(captcha_answer)
        },
        content_type="multipart/form-data"
    )

    assert response.status_code == 200
    assert "Разрешены только JPG, JPEG и PNG!".encode("utf-8") in response.data
