class FormatError(Exception):
    """Ошибка несоответствия формата ожидаемому."""
    pass


class UnexpectedHTTPStatusError(Exception):
    """Неожиданный HTTP статус."""
    pass


class TokenViolationError(Exception):
    """Ошибка при парсинге переменных окружения."""
    pass


class EmptyAPIResponse(Exception):
    """Получен пустой ответ от API-сервера."""
    pass
