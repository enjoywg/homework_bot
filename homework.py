import logging
import os
import time

import requests
import telegram
from dotenv import load_dotenv

from exceptions import NoAnswerError, SendMessageError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 1
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

handler = logging.StreamHandler()
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.DEBUG,
    handlers=[handler],
)


def send_message(bot, message):
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logging.info('Сообщение отправлено')
    except SendMessageError:
        logging.error('Сбой при отправке сообщения в Telegram')


def get_api_answer(current_timestamp):
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except NoAnswerError:
        logging.error('Эндпоинт недоступен')
        raise NoAnswerError('Эндпоинт недоступен')
    if response.status_code != 200:
        logging.error('Сбой при запросе к эндпоинту')
        raise Exception('Сбой при запросе к эндпоинту')
    return response.json()


def check_response(response):
    if type(response) is not dict:
        logging.error('Тип ответа API - не словарь')
    if 'homeworks' not in response:
        logging.error('Неправильный формат ответа API')
    homeworks = response['homeworks']
    try:
        homeworks[0]
    except IndexError:
        logging.debug('Нет новых статусов домашек')

    return homeworks


def parse_status(homework):
    if ('homework_name' or 'status') not in homework:
        logging.error('Некорректный формат данных homework')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        logging.error('Недокументированный статус домашней работы обнаружен'
                      ' в ответе API')
        raise KeyError('Недокументированный статус домашней работы обнаружен'
                       ' в ответе API')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    if None in [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]:
        return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Отсутствие обязательных переменных окружения во '
                         'время запуска бота')
        raise SystemExit('Проверьте, заданы ли все токены')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                send_message(bot, message)
            current_timestamp = int(time.time())

            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)

            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
