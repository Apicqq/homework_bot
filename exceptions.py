class FormatError(Exception):
    """Ошибка несоответствия формата ожидаемому."""
    pass


class EndpointError(Exception):
    """Ошибка на стороне API-сервиса."""
    pass


class UnexpectedHTTPStatusError(Exception):
    """Неожиданный HTTP статус."""
    pass


class TokenViolationError(Exception):
    """Ошибка при парсинге переменных окружения."""
    pass