
import os
import re
import uuid
import random

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from flask import (
    Flask,
    render_template,
    request,
    url_for,
    session
)

from PIL import (
    Image,
    ImageDraw,
    UnidentifiedImageError
)

from werkzeug.exceptions import RequestEntityTooLarge


# ==========================================
# 1. НАСТРОЙКА ПУТЕЙ
# ==========================================

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
RESULT_FOLDER = os.path.join(BASE_DIR, 'static', 'results')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)


# ==========================================
# 2. СОЗДАНИЕ FLASK-ПРИЛОЖЕНИЯ
# ==========================================

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static'),
    static_url_path='/static'
)

# Секретный ключ для работы сессий
app.secret_key = os.environ.get(
    'SECRET_KEY',
    'development-secret-key-change-me'
)

# Максимальный размер файла — 5 МБ
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

# Разрешённые форматы
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

# Максимальное количество пикселей
MAX_IMAGE_PIXELS = 20_000_000


# ==========================================
# 3. ПРОВЕРКА РАСШИРЕНИЯ ФАЙЛА
# ==========================================

def allowed_file(filename):
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    )


# ==========================================
# 4. ПРОВЕРКА ИЗОБРАЖЕНИЯ
# ==========================================

def validate_image(file):

    try:
        file.seek(0)

        with Image.open(file) as image:

            if image.format not in ('JPEG', 'PNG'):
                return False

            width, height = image.size

            if (
                width <= 0
                or height <= 0
                or width * height > MAX_IMAGE_PIXELS
            ):
                return False

            image.verify()

        file.seek(0)

        with Image.open(file) as image:
            image.load()

        return True

    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError
    ):
        return False

    finally:
        file.seek(0)


# ==========================================
# 5. ПОЛУЧЕНИЕ ИНФОРМАЦИИ ОБ ИЗОБРАЖЕНИИ
# ==========================================

def get_image_info(file_path):

    with Image.open(file_path) as image:

        width, height = image.size

        return {
            'width': width,
            'height': height,
            'format': image.format,
            'mode': image.mode
        }


# ==========================================
# 6. РИСОВАНИЕ КРЕСТА
# ==========================================

def draw_cross(
    image_path,
    output_path,
    color,
    thickness,
    orientation
):
    """
    Рисует вертикальную или горизонтальную линию
    по центру изображения.
    """

    with Image.open(image_path) as original:
        image = original.convert('RGB')

    width, height = image.size

    center_x = width // 2
    center_y = height // 2

    draw = ImageDraw.Draw(image)

    if orientation == 'vertical':

        draw.line(
            [(center_x, 0), (center_x, height - 1)],
            fill=color,
            width=thickness
        )

    elif orientation == 'horizontal':

        draw.line(
            [(0, center_y), (width - 1, center_y)],
            fill=color,
            width=thickness
        )

    image.save(output_path, format='PNG')

    return output_path


# ==========================================
# 7. ПОСТРОЕНИЕ RGB-ГИСТОГРАММЫ
# ==========================================

def create_histogram(image_path, output_path, title):

    """
    Строит график распределения красного,
    зелёного и синего каналов изображения.
    """

    with Image.open(image_path) as image:

        image = image.convert('RGB')

        red, green, blue = image.split()

        red_hist = red.histogram()
        green_hist = green.histogram()
        blue_hist = blue.histogram()

    fig, ax = plt.subplots(figsize=(10, 5))

    values = range(256)

    ax.plot(
        values,
        red_hist,
        color='red',
        label='Красный (R)'
    )

    ax.plot(
        values,
        green_hist,
        color='green',
        label='Зелёный (G)'
    )

    ax.plot(
        values,
        blue_hist,
        color='blue',
        label='Синий (B)'
    )

    ax.set_title(title)
    ax.set_xlabel('Интенсивность цвета')
    ax.set_ylabel('Количество пикселей')

    ax.set_xlim(0, 255)

    ax.legend()
    ax.grid(alpha=0.3)

    fig.tight_layout()

    fig.savefig(output_path, dpi=120)

    plt.close(fig)

    return output_path


# ==========================================
# 8. ГЕНЕРАЦИЯ CAPTCHA
# ==========================================

def generate_captcha():

    """
    Создаёт простой математический пример.
    """

    a = random.randint(1, 10)
    b = random.randint(1, 10)

    question = f'{a} + {b}'
    answer = a + b

    session['captcha_answer'] = answer

    return question


# ==========================================
# 9. ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ОТОБРАЖЕНИЯ
# ==========================================

def render_page(error=None, success=None, **kwargs):

    question = generate_captcha()

    return render_template(
        'index.html',
        error=error,
        success=success,
        captcha_question=question,
        **kwargs
    )


# ==========================================
# 10. ГЛАВНАЯ СТРАНИЦА
# ==========================================

@app.route('/', methods=['GET', 'POST'])
def index():

    # Открытие страницы
    if request.method == 'GET':

        return render_page()

    # ======================================
    # ПРОВЕРКА CAPTCHA
    # ======================================

    user_answer = request.form.get('captcha_answer', '')

    correct_answer = session.pop('captcha_answer', None)

    try:
        user_answer = int(user_answer)
    except (ValueError, TypeError):
        user_answer = -1

    if correct_answer is None or user_answer != correct_answer:

        return render_page(
            error='Неправильный ответ CAPTCHA!'
        )

    # ======================================
    # ПОЛУЧЕНИЕ ФАЙЛА
    # ======================================

    file = request.files.get('image')

    if file is None or file.filename == '':

        return render_page(
            error='Выберите изображение!'
        )

    # Проверка расширения
    if not allowed_file(file.filename):

        return render_page(
            error='Разрешены только JPG, JPEG и PNG!'
        )

    # Проверка содержимого
    if not validate_image(file):

        return render_page(
            error='Файл повреждён или не является изображением!'
        )

    # ======================================
    # ПОЛУЧЕНИЕ ПАРАМЕТРОВ
    # ======================================

    color = request.form.get('color', '#ff0000')

    if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):

        return render_page(
            error='Некорректный цвет креста!'
        )

    try:

        thickness = int(request.form.get('thickness', '5'))

    except (ValueError, TypeError):

        return render_page(
            error='Толщина должна быть целым числом!'
        )

    if not 1 <= thickness <= 30:

        return render_page(
            error='Толщина должна быть от 1 до 30 пикселей!'
        )

    # Проверка ориентации
    orientation = request.form.get('orientation', 'vertical')

    if orientation not in ('vertical', 'horizontal'):

        return render_page(
            error='Выберите правильную ориентацию!'
        )

    # ======================================
    # СОХРАНЕНИЕ ИЗОБРАЖЕНИЯ
    # ======================================

    unique_id = uuid.uuid4().hex

    original_name = unique_id + '_original.png'

    original_path = os.path.join(
        UPLOAD_FOLDER,
        original_name
    )

    result_name = unique_id + '_result.png'

    result_path = os.path.join(
        RESULT_FOLDER,
        result_name
    )

    original_hist_name = unique_id + '_original_hist.png'

    original_hist_path = os.path.join(
        RESULT_FOLDER,
        original_hist_name
    )

    result_hist_name = unique_id + '_result_hist.png'

    result_hist_path = os.path.join(
        RESULT_FOLDER,
        result_hist_name
    )

    try:

        # Сохраняем исходное изображение
        with Image.open(file) as image:

            image = image.convert('RGB')
            image.save(original_path, format='PNG')

        # Получаем характеристики
        image_info = get_image_info(original_path)

        # Рисуем крест
        draw_cross(
            original_path,
            result_path,
            color,
            thickness,
            orientation
        )

        # Строим гистограмму оригинала
        create_histogram(
            original_path,
            original_hist_path,
            'Распределение цветов исходного изображения'
        )

        # Строим гистограмму обработанного изображения
        create_histogram(
            result_path,
            result_hist_path,
            'Распределение цветов обработанного изображения'
        )

    except (
        OSError,
        ValueError,
        Image.DecompressionBombError
    ):

        return render_page(
            error='Не удалось обработать изображение!'
        )

    # ======================================
    # ФОРМИРОВАНИЕ ССЫЛОК
    # ======================================

    image_url = url_for(
        'static',
        filename='uploads/' + original_name
    )

    result_url = url_for(
        'static',
        filename='results/' + result_name
    )

    original_hist_url = url_for(
        'static',
        filename='results/' + original_hist_name
    )

    result_hist_url = url_for(
        'static',
        filename='results/' + result_hist_name
    )

    # ======================================
    # ВОЗВРАЩАЕМ РЕЗУЛЬТАТ
    # ======================================

    return render_page(
        success='Изображение успешно обработано!',

        image_url=image_url,
        result_url=result_url,

        original_hist_url=original_hist_url,
        result_hist_url=result_hist_url,

        image_info=image_info,

        selected_color=color,
        selected_thickness=thickness,
        selected_orientation=orientation
    )


# ==========================================
# 11. СТРАНИЦА О ПРИЛОЖЕНИИ
# ==========================================

@app.route('/about')
def about():

    return """
        <h1>О приложении</h1>

        <p>
            Веб-приложение для обработки изображений.
        </p>

        <p>
            Лабораторная работа. Вариант 10.
        </p>

        <a href="/">Вернуться на главную</a>
    """


# ==========================================
# 12. ОБРАБОТКА ОШИБКИ РАЗМЕРА ФАЙЛА
# ==========================================

@app.errorhandler(RequestEntityTooLarge)
def file_too_large(error):

    return render_page(
        error='Размер изображения не должен превышать 5 МБ!'
    ), 413


# ==========================================
# 13. ЗАПУСК ПРИЛОЖЕНИЯ
# ==========================================

if __name__ == '__main__':

    print('Папка проекта:', BASE_DIR)
    print('Папка загрузок:', UPLOAD_FOLDER)
    print('Папка результатов:', RESULT_FOLDER)

    app.run(debug=True)
