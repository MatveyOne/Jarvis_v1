import sqlite3  # Импорт модуля sqlite3 для работы с базами данных SQLite.
import logging  # Импорт модуля logging для ведения журнала логов.
from config import DB_FILE, LOGS, N_LAST_MESSAGE # Импорт настроек путей к файлу базы данных и файлу логов.

logging.basicConfig(filename=LOGS, level=logging.INFO)  # Настройка журналирования с записью в файл LOGS и уровнем INFO.

def create_database():
    try:
        with sqlite3.connect(DB_FILE) as conn:  # Установление соединения с базой данных
            cursor = conn.cursor()  # Создание курсора
            cursor.execute('''CREATE TABLE IF NOT EXISTS messages (
                                id INTEGER PRIMARY KEY,
                                user_id INTEGER,
                                message TEXT,
                                role TEXT,
                                total_gpt_tokens INTEGER,
                                tts_symbols INTEGER,
                                stt_blocks INTEGER)
                            ''')  # Создание таблицы сообщений, если её нет
            conn.commit()  # Подтверждение изменений в базе данных
            logging.info("DATABASE: Table 'messages' has been created successfully.")  # Журналирование успешного создания таблицы
    except Exception as e:  # Обработка исключений
        logging.error(f"DATABASE: Failed to create database - {e}")  # Журналирование ошибки при создании таблицы
        raise e  # Повторное возбуждение исключения для его отображения в консоли
        print(f"Error: {e}")  # Вывод ошибки, если операция не удалась

def add_message(user_id, message, role, total_gpt_tokens=0, tts_symbols=0, stt_blocks=0):
    logging.info(f"Attempting to add message: user_id={user_id}, role={role}, total_gpt_tokens={total_gpt_tokens}, tts_symbols={tts_symbols}, stt_blocks={stt_blocks}")
    try:
        with sqlite3.connect(DB_FILE) as conn:  # Установление соединения с базой данных
            cursor = conn.cursor()  # Создание курсора
            # Получение последних значений из базы данных для данной роли
            last_values = cursor.execute('''SELECT total_gpt_tokens, tts_symbols, stt_blocks FROM messages WHERE user_id=? AND role=? ORDER BY id DESC LIMIT 1''', (user_id, role)).fetchone()
            # Если записи отсутствуют, устанавливаем начальные значения
            if last_values:
                total_gpt_tokens += last_values[0]
                tts_symbols += last_values[1]
                stt_blocks += last_values[2]

            cursor.execute('''
                INSERT INTO messages (user_id, message, role, total_gpt_tokens, tts_symbols, stt_blocks)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, message, role, total_gpt_tokens, tts_symbols, stt_blocks))  # Вставка сообщения в базу данных
            conn.commit()  # Подтверждение изменений
    except Exception as e:  # Обработка исключений
        logging.error(f"Failed to add message for user_id={user_id}, error: {e}")  # Журналирование ошибки при добавлении сообщения


def select_n_last_messages(user_id, n_last_messages=N_LAST_MESSAGE):  # Функция для выбора последних сообщений пользователя.
    messages = []  # Инициализация списка сообщений.
    total_spent_tokens = 0  # Счетчик потраченных токенов.
    try:
        with sqlite3.connect(DB_FILE) as conn:  # Открытие соединения с базой данных.
            cursor = conn.cursor()  # Создание курсора.
            cursor.execute('''
                SELECT message, role, total_gpt_tokens FROM messages WHERE user_id=? ORDER BY id DESC LIMIT ?
            ''', (user_id, n_last_messages))  # SQL-запрос для выбора последних сообщений.
            data = cursor.fetchall()  # Получение результатов запроса.
            if data:  # Проверка, есть ли данные.
                for message in reversed(data):  # Перебор сообщений в обратном порядке.
                    messages.append({'text': message[0], 'role': message[1]})  # Добавление сообщения в список.
                    total_spent_tokens = max(total_spent_tokens, message[2])  # Обновление счетчика токенов.
            return messages, total_spent_tokens  # Возвращение списка сообщений и счетчика токенов.
    except Exception as e:  # Обработка исключений.
        logging.error(f"DATABASE: Error retrieving last {n_last_messages} messages for user_id={user_id}, error: {e}")  # Запись ошибки в лог.
        return messages, total_spent_tokens  # Возврат значений по умолчанию в случае ошибки.

def count_all_limits(user_id, limit_type):  # Функция подсчета использованных ресурсов пользователя.
    try:
        with sqlite3.connect(DB_FILE) as conn:  # Открытие соединения с базой данных.
            cursor = conn.cursor()  # Создание курсора.
            cursor.execute(f"SELECT SUM({limit_type}) FROM messages WHERE user_id=?", (user_id,))  # SQL-запрос на подсчет суммы ресурса.
            data = cursor.fetchone()  # Получение результата запроса.
            if data and data[0] is not None:  # Проверка, есть ли результат.
                return data[0]  # Возвращение результата.
            return 0  # Возврат 0, если данных нет.
    except Exception as e:  # Обработка исключений.
        logging.error(f"DATABASE: Error counting {limit_type} for user_id={user_id}, error: {e}")  # Запись ошибки в лог.
        return 0  # Возврат 0 при наличии ошибки.


def count_all_blocks(user_id, db_name=DB_FILE):  # Функция подсчёта всех использованных аудиоблоков.
    try:
        with sqlite3.connect(db_name) as conn:  # Установление соединения с базой данных
            cursor = conn.cursor()  # Создание курсора
            cursor.execute('''SELECT SUM(stt_blocks) FROM messages WHERE user_id=?''', (user_id,))  # Выполнение SQL-запроса для подсчета суммы использованных аудиоблоков
            data = cursor.fetchone()  # Получение результата запроса
            if data and data[0]:  # Проверка, есть ли данные в ответе
                return data[0]  # Возврат суммы использованных аудиоблоков
            else:
                return 0  # Возврат 0, если данные отсутствуют
    except Exception as e:  # Обработка исключений
        logging.error(f"DATABASE: Error in count_all_blocks for user_id={user_id}, error: {e}")  # Журналирование ошибки
        return 0  # Возврат 0 при наличии ошибки


    # # Файл database.py
    #
    # import sqlite3
    # import logging
    # from config import DB_FILE, LOGS
    #
    # logging.basicConfig(filename=LOGS, level=logging.INFO)
    #
    # def count_all_limits(user_id, limit_type):
    #     try:
    #         with sqlite3.connect(DB_FILE) as conn:
    #             cursor = conn.cursor()
    #             cursor.execute(f"SELECT SUM({limit_type}) FROM messages WHERE user_id=?", (user_id,))
    #             data = cursor.fetchone()
    #             return data[0] if data[0] is not None else 0
    #     except Exception as e:
    #         logging.error(f"DATABASE: Error counting {limit_type} for user_id={user_id}, error: {e}")
    #         return 0
    #
    # # Файл main.py
    #
    # from database import select_n_last_messages, add_message, count_all_limits
    # from config import MAX_USER_STT_BLOCKS, MAX_USER_TTS_SYMBOLS, MAX_USER_GPT_TOKENS, MAX_USERS
    # from yandex_gpt import ask_gpt
    # from speech_kit import text_to_speech
    # import time
    # from threading import Lock
    #
    # active_sessions = {}
    # session_lock = Lock()
    #
    # def manage_user_session(user_id):
    #     with session_lock:
    #         current_time = time.time()
    #         active_sessions[user_id] = current_time
    #         for user in list(active_sessions):
    #             if current_time - active_sessions[user] > 60:  # TIME_NOT_ACTIVE
    #                 del active_sessions[user]
    #
    # def process_and_respond(bot, user_id, text, duration):
    #     manage_user_session(user_id)
    #     messages, _ = select_n_last_messages(user_id, 5)
    #     context = [m['text'] for m in messages] + [text]
    #     response, tokens_used = process_message(text, user_id, context)
    #     if response:
    #         response_trimmed = response[:MAX_USER_TTS_SYMBOLS]
    #         tts_symbols_count = len(response_trimmed)
    #     else:
    #         response_trimmed = response
    #         tts_symbols_count = 0
    #
    #     total_gpt_tokens = count_all_limits(user_id, 'total_gpt_tokens') + tokens_used if tokens_used else 0
    #     audio_blocks = (duration // 15) + (1 if duration % 15 > 0 else 0)
    #
    #     add_message(user_id, text, 'user', total_gpt_tokens=total_gpt_tokens, stt_blocks=audio_blocks)
    #     add_message(user_id, response_trimmed, 'bot', total_gpt_tokens=total_gpt_tokens, tts_symbols=tts_symbols_count)
    #
    #     if duration > 0:
    #         voice_status, voice_message = text_to_speech(response_trimmed)
    #         if voice_status:
    #             bot.send_voice(user_id, voice_message)
    #         else:
    #             bot.send_message(user_id, "Ошибка при генерации голосового сообщения.")
    #     else:
    #         bot.send_message(user_id, response_trimmed)
    #
    # def process_message(text, user_id, context):
    #     total_text = " ".join(context)
    #     if count_all_limits(user_id, 'total_gpt_tokens') + len(total_text) > MAX_USER_GPT_TOKENS:
    #         return "Превышен лимит токенов GPT.", None
    #     status, response, tokens_used = ask_gpt([{'role': 'user', 'text': total_text}])
    #     if status:
    #         return response, tokens_used
    #     return
