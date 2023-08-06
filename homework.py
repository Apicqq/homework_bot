import logging
import os
import sys
import time
from json import JSONDecodeError
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (
    EmptyAPIResponse,
    FormatError,
    TokenViolationError,
    UnexpectedHTTPStatusError,
)

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

TOKEN_ERROR = ('Ошибка глобальной переменной.'
               ' Выполнение программы остановлено.')
TG_API_ERROR = 'При отправке сообщения в Telegram возникла ошибка: {}'
CONNECTION_ERROR = 'Эндпоинт {} недоступен. Переданные параметры: {}, {}'
WRONG_HTTP_STATUS_ERROR = 'Вернулся неожиданный HTTP статус: {}'
ATTRIBUTE_ERROR = 'Формат не соответствует ожидаемому: {}'
NOT_DICT_ERROR = (
    'Тип данных в ответе от сервера не соответствует ожидаемому. '
    'Получен: {}')
EMPTY_API_ERROR = 'Получен пустой запрос от API: {}'
NOT_LIST_ERROR = ('Тип данных для извлечения не соответствует ожидаемому.'
                  ' Получен: {}')
UNEXPECTED_HOMEWORK_ERROR = 'Неожиданный статус домашней работы: {}'
HOMEWORK_PARSING_ERROR = 'Получены некорректные данные: {}, {}'
GLOBAL_EXCEPTION_ERROR = 'Сбой в работе программы: {}'

logger = logging.getLogger(__name__)


def check_tokens():
    """
    Проверяем доступность переменных окружения.
    Если отсутствует хотя бы одна — программа останавливается,
    далее продолжать работу бота нет смысла.
    """
    values = (
        ('PRACTICUM_TOKEN', PRACTICUM_TOKEN),
        ('TELEGRAM_TOKEN', TELEGRAM_TOKEN),
        ('TELEGRAM_CHAT_ID', TELEGRAM_CHAT_ID)
    )
    value_is_present = True
    for key, value in values:
        if not value:
            logger.critical(f'Переменная окружения {key} не указана.'
                            ' Выполнение программы остановлено.')
            value_is_present = False
        if not value_is_present:
            raise TokenViolationError(TOKEN_ERROR)
        return value_is_present


def send_message(bot, message):
    """Отправляем сообщение пользователю в Telegram."""
    logger.debug(f'Попытка отправки сообщения: {message}')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Сообщение "{message}" успешно отправлено.')
        return True
    except telegram.error.TelegramError as error:
        logger.error(TG_API_ERROR.format(error))
        return False


def get_api_answer(timestamp):
    """Получаем API-response от эндпоинта Яндекс.Домашка."""
    all_params = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp}
    }
    logger.debug('Попытка отправки запроса к эндпоинту: {url} с параметрами:'
                 ' {headers} - {params}'.format(**all_params))
    try:
        response = requests.get(**all_params)
        logger.debug('Запрос к эндпоинту успешно отправлен.')
    except requests.exceptions.RequestException:
        raise ConnectionError(CONNECTION_ERROR.format(**all_params))
    if response.status_code != HTTPStatus.OK:
        raise UnexpectedHTTPStatusError(
            WRONG_HTTP_STATUS_ERROR.format(response.status_code)
        )
    try:
        logger.debug('Ответ на запрос API от эндпоинта получен.')
        return response.json()
    except JSONDecodeError as error:
        raise FormatError(ATTRIBUTE_ERROR.format(error))


def check_response(response):
    """Валидируем входящий ответ от сервера."""
    if not isinstance(response, dict):
        raise TypeError(NOT_DICT_ERROR.format(type(response)))
    if 'homeworks' not in response:
        raise EmptyAPIResponse(EMPTY_API_ERROR.format(response))
    homework_status = response.get('homeworks')
    if not isinstance(homework_status, list):
        raise TypeError(NOT_LIST_ERROR.format(type(homework_status)))
    return homework_status


def parse_status(homework):
    """
    Парсим статус проверки.
    Кроме того, преобразуем полученный ответ
    от сервера из JSON к Python.
    """
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(UNEXPECTED_HOMEWORK_ERROR.format(homework_status))
    if not homework_name or not homework_status:
        raise ValueError(HOMEWORK_PARSING_ERROR.format(
            homework_name, homework_status
        ))
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 0
    current_report = {'output': ''}
    previous_report = {'output': ''}
    while True:
        try:
            logger.debug('Бот начал работу.')
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework:
                current_report['output'] = parse_status(homework[0])
            else:
                current_report['output'] = 'Статус проекта не обновился.'
            if current_report != previous_report:
                send_message(bot, current_report['output'])
                if send_message:
                    previous_report = current_report.copy()
                    timestamp = response.get('current_date', timestamp)
            else:
                logger.info('Статус проекта не обновился.')
        except EmptyAPIResponse as error:
            logger.error(EMPTY_API_ERROR.format(error))
        except Exception as error:
            message = GLOBAL_EXCEPTION_ERROR.format(error)
            current_report['output'] = message
            logger.error(message)
            if current_report != previous_report:
                send_message(bot, message)
                previous_report = current_report.copy()
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    sys_handler = logging.StreamHandler(sys.stdout)
    file_handler = logging.FileHandler(__file__ + '.log', encoding='utf-8')
    formatter = logging.Formatter(
        '%(levelname)s - %(asctime)s - %(lineno)s - %(funcName)s - '
        '%(message)s - %(name)s')
    sys_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(sys_handler)
    main()
