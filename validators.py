from database import select_n_last_messages, add_message, count_all_blocks, count_all_limits
from config import MAX_USER_STT_BLOCKS, MAX_USER_GPT_TOKENS, MAX_USER_TTS_SYMBOLS, MAX_TIME_VOICE, MAX_USERS, TIME_NOT_ACTIVE
from yandex_gpt import ask_gpt
from speech_kit import text_to_speech
import time
from threading import Lock

active_sessions = {}  # Словарь для отслеживания активных сессий пользователей
session_lock = Lock()  # Создание объекта блокировки для безопасного доступа к активным сессиям

def manage_user_session(user_id):
    with session_lock:  # Использование блокировки для безопасного доступа к активным сессиям
        current_time = time.time()  # Получение текущего времени
        active_sessions[user_id] = current_time  # Обновление времени активной сессии для данного пользователя
        # Очистка неактивных сессий
        for user in list(active_sessions):  # Итерация по копии списка активных сессий
            if current_time - active_sessions[user] > TIME_NOT_ACTIVE:  # Проверка времени неактивности пользователя
                del active_sessions[user]  # Удаление неактивной сессии из словаря

def is_under_user_limit():
    manage_user_session(None)  # Обновление активных сессий без добавления новой
    return len(active_sessions) < MAX_USERS  # Проверка, не превышен ли лимит активных пользователей

def is_user_active(user_id):
    manage_user_session(None)  # Обновление активных сессий
    return user_id in active_sessions  # Проверка, активен ли пользователь

def process_message(text, user_id, context):
    total_text = " ".join(context)  # Объединение текста контекста
    if count_all_limits(user_id, 'total_gpt_tokens') + len(total_text) > MAX_USER_GPT_TOKENS:  # Проверка лимита токенов GPT
        return "Превышен лимит токенов GPT.", None  # Возврат сообщения об ошибке, если превышен лимит
    status, response, tokens_used = ask_gpt([{'role': 'user', 'text': total_text}])  # Запрос к GPT
    if status:
        return response, tokens_used  # Возврат ответа и использованных токенов
    return "Ошибка при обращении к GPT.", None  # Возврат сообщения об ошибке при обращении к GPT

def check_voice_limits(user_id, duration):
    current_blocks = (duration // 15) + (1 if duration % 15 > 0 else 0)  # Вычисление текущего количества аудиоблоков
    total_blocks = count_all_blocks(user_id) + current_blocks  # Вычисление общего количества аудиоблоков
    if total_blocks > MAX_USER_STT_BLOCKS:  # Проверка лимита аудиоблоков
        return False, 'Превышен лимит аудиоблоков.', current_blocks  # Возврат сообщения об ошибке, если превышен лимит
    return True, None, current_blocks  # Возврат успеха без сообщения об ошибке, если лимит не превышен


# def check_voice_limits(user_id, duration):
#     if duration >= MAX_TIME_VOICE:
#         return False, "SpeechKit STT работает с голосовыми сообщениями меньше 30 секунд.", 0
#     audio_blocks = (duration // 15) + (1 if duration % 15 > 0 else 0)
#     all_blocks = count_all_blocks(user_id)
#     if all_blocks + audio_blocks > MAX_USER_STT_BLOCKS:
#         return False, 'Превышен лимит аудиоблоков.', audio_blocks
#     return True, None, audio_blocks

# def check_voice_limits(user_id, duration):
#     if duration >= MAX_TIME_VOICE:
#         return False, "SpeechKit STT работает с голосовыми сообщениями меньше 30 секунд."
#     audio_blocks = (duration // 15) + (1 if duration % 15 > 0 else 0)
#     all_blocks = count_all_blocks(user_id)
#     if all_blocks + audio_blocks > MAX_USER_STT_BLOCKS:
#         return False, 'Превышен лимит аудиоблоков.'
#     return True, None


def process_and_respond(bot, user_id, text, duration):
    manage_user_session(user_id)  # Обновление активной сессии пользователя
    messages, _ = select_n_last_messages(user_id, 5)  # Получение последних 5 сообщений пользователя
    context = [m['text'] for m in messages] + [text]  # Формирование контекста из последних сообщений и текущего текста
    response, tokens_used = process_message(text, user_id, context)  # Обработка сообщения и получение ответа от бота

    if response is None:  # Проверка на наличие ответа
        response = "Произошла ошибка, попробуйте ещё раз."  # Установка сообщения об ошибке в случае отсутствия ответа

    response_trimmed = response[:MAX_USER_TTS_SYMBOLS] if len(response) > MAX_USER_TTS_SYMBOLS else response  # Обрезка ответа до максимального количества символов для синтеза речи
    tts_symbols_count = len(response_trimmed)  # Подсчет количества символов в обрезанном ответе

    success, msg, audio_blocks = check_voice_limits(user_id, duration)  # Проверка лимитов для голосовых сообщений
    if not success:  # Если лимиты превышены
        bot.send_message(user_id, msg)  # Отправка сообщения об ошибке
        return

    total_gpt_tokens = count_all_limits(user_id, 'total_gpt_tokens') + tokens_used  # Обновление счетчика GPT токенов после получения ответа от бота

    add_message(user_id, text, 'user', 0, 0, audio_blocks if duration > 0 else 0)  # Сохранение исходного сообщения пользователя
    add_message(user_id, response_trimmed, 'bot', total_gpt_tokens, tts_symbols_count, 0)  # Сохранение ответа от бота

    if duration > 0:  # Если длительность голосового сообщения больше нуля
        voice_status, voice_message = text_to_speech(response_trimmed)  # Синтез речи из ответа
        if voice_status:  # Если синтез прошел успешно
            bot.send_voice(user_id, voice_message)  # Отправка синтезированного голосового сообщения
        else:
            bot.send_message(user_id, "Ошибка при генерации голосового сообщения.")  # Отправка сообщения об ошибке при синтезе речи
    else:
        bot.send_message(user_id, response_trimmed)  # Отправка обрезанного ответа от бота



# def process_and_respond(bot, user_id, text, duration):
#     manage_user_session(user_id)
#     messages, total_spent_tokens = select_n_last_messages(user_id, 5)
#     context = [m['text'] for m in messages] + [text]
#     response, _ = process_message(text, user_id, context)
#     if len(response) > MAX_USER_TTS_SYMBOLS:
#         response = response[:MAX_USER_TTS_SYMBOLS]
#     total_gpt_tokens = count_all_limits(user_id, 'total_gpt_tokens') + len(" ".join(context))
#     add_message(user_id, text, 'user', total_gpt_tokens=total_gpt_tokens, stt_blocks=(duration // 15) + (1 if duration % 15 > 0 else 0))
#     add_message(user_id, response, 'bot', total_gpt_tokens=total_gpt_tokens)
#     if duration > 0:
#         voice_status, voice_message = text_to_speech(response)
#         if voice_status:
#             bot.send_voice(user_id, voice_message)
#         else:
#             bot.send_message(user_id, "Ошибка при генерации голосового сообщения.")
#     else:
#         bot.send_message(user_id, response)

