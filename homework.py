import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

import exceptions as _

load_dotenv()

PRACTICUM_TOKEN = os.getenv('YA_TOKEN')
TELEGRAM_TOKEN = os.getenv('TG_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('MY_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


# def check_tokens():
#     """
#     Проверяем доступность переменных окружения.
#     Если отсутствует хотя бы одна — программа останавливается,
#     далее продолжать работу бота нет смысла.
#     """
#     for key in (PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID):
#         if key is None:
#             logging.critical(f'Переменная окружения {key} отсутствует.'
#                              ' Выполнение программы остановлено.')
#             return False
#         elif not key:
#             logging.critical(f'Переменная окружения {key} не указана.'
#                              ' Выполнение программы остановлено.')
#             return False
#     return True
#  Не смог решить, какой вариант будет использовать лучше, подскажи,
#  пожалуйста
def check_tokens():
    """
    Проверяем доступность переменных окружения.
    Если отсутствует хотя бы одна — программа останавливается,
    далее продолжать работу бота нет смысла.
    """
    validated_tokens = all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID))
    if not validated_tokens:
        logging.critical('Возникла ошибка при проверке переменных окружения.'
                         ' Выполнение программы остановлено.')
    return validated_tokens


def send_message(bot, message):
    """Отправляем сообщение пользователю в Telegram."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Сообщение "{message}" успешно отправлено')
    # except telegram.error.BadRequest as e:
    #     logging.error(f'API Телеграма не удалось обработать запрос: {e}')
    # except telegram.error.NetworkError as e:
    #     logging.error(f'Не удалось установить соединение с API '
    #                   f'Телеграма: {e}')
    # except telegram.error.Unauthorized as e:
    #     logging.error(f'У бота недостаточно прав для совершения'
    #                   f' следующего действия: {e}')
    except telegram.error.TelegramError as e:
        message = ('При отправке сообщения в Telegram возникла'
                   f' ошибка: {e}')
        logging.error(message)
        raise _.EndpointError(message)
    #  Хотел логирование сделать более конкретным, но тесты хотят видеть только
    #  родительский класс ошибки из телеграма :(


def get_api_answer(timestamp):
    """Получаем API-response от эндпоинта Яндекс.Домашка."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
    except requests.exceptions.RequestException as e:
        message = f'Эндпоинт Практикума недоступен. Причина: {e}'
        logging.error(message)
        raise _.EndpointError(message)
    if response.status_code != HTTPStatus.OK:
        message = ('Вернулся неожиданный HTTP статус:'
                   f' {response.status_code}')
        logging.error(message)
        raise _.UnexpectedHTTPStatusError(message)
    try:
        return response.json()
    except TypeError as e:
        message = f'Формат не соответствует ожидаемому: {e}'
        logging.error(message)
        raise _.FormatError(message)


def check_response(response):
    """Валидируем входящий ответ от сервера."""
    if not isinstance(response, dict):
        message = (f'Тип данных в ответе от сервера не соответствует '
                   f'ожидаемому. Получен: {type(response)}')
        logging.error(message)
        raise TypeError(message)
    elif 'homeworks' not in response:
        message = 'Ключ homeworks недоступен.'
        logging.error(message)
        raise KeyError(message)
    elif not isinstance(response.get('homeworks'), list):
        message = (f'Тип данных для извлечения не соответствует'
                   f' ожидаемому. Получен: {type(response.get("homeworks"))}')
        logging.error(message)
        raise TypeError(message)
    return response.get('homeworks')


def parse_status(homework):
    """
    Парсим статус проверки.
    Кроме того, преобразуем полученный ответ
    от сервера из JSON в читаемый вид.
    """
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if (homework_status not in HOMEWORK_VERDICTS or homework_name is None
            or homework_status is None):
        message = 'Получены данные некорректного типа.'
        logging.error(message)
        raise ValueError(message)
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise _.TokenViolationError('Ошибка глобальной переменной.'
                                    ' Выполнение программы остановлено.')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if not homework:
                message = ('Статус проекта не изменился. '
                           'Ожидаем...')
                logging.info(message)
                send_message(bot, message)
            else:
                homework_status = parse_status(next(iter(homework)))
                send_message(bot, homework_status)
        except Exception as e:
            message = f'Сбой в работе программы: {e}'
            send_message(bot, message)
            logging.error(send_message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(levelname)s, - %(message)s - %(name)s',
        level=logging.DEBUG
    )
    logger = logging.getLogger(__name__)
    handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(handler)
    main()
