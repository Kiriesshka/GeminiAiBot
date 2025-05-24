import requests
import os

MAX_MESSAGE_LENGTH=4000

class Colors:
    red = "\033[31m"
    green = "\033[32m"
    yellow = "\033[33m"
    blank = "\033[0m"
class CORE:
    "класс - ядро системы, здесь собраны основные функции для работы, можно модифицировать для любого поведения."
    @staticmethod
    def make_request_to_genai(bot,markup,user,message,model)->bool:
        """
        Отправляет запрос gemini напрямую через google.generativeai api
        """
        try:
            response_text=CORE.get_response_genai(user,message,model)
            if response_text=="Error":
                return False
            while len(user.history) > user.memory_deep:
                user.history.pop(0)
            parts = [response_text[i:i+MAX_MESSAGE_LENGTH] for i in range(0, len(response_text), MAX_MESSAGE_LENGTH)]
            for i in parts[:-1]:
                bot.send_message(chat_id=message.chat.id, message_thread_id = message.message_thread_id, text = i)
            bot.send_message(chat_id=message.chat.id, message_thread_id = message.message_thread_id, text = parts[-1], reply_markup=markup)
            return True
        except Exception as e:
            Debug.log_error(f"CORE ERROR: {str(e)}")
            return False
    @staticmethod
    def cli_make_request_to_genai(user,message,model)->bool:
        """
        Отправляет запрос gemini напрямую через google.generativeai api, выводит результат в консоль
        """
        try:
            response_text=CORE.get_response_genai(user,message,model)
            if response_text=="Error":
                return False
            print(f"AI > \n    {response_text}")
            return True
        except Exception as e:
            Debug.log_error(f"CORE ERROR: {str(e)}")
            return False
    @staticmethod
    def get_response_genai(user, message, model):
        """
        Отправляет запрос gemini напрямую через google.generativeai api и возвращает строку; в случае ошибки вернет Error
        """
        try:
            chat_session = model.start_chat(
                history=user.history
            )
            response = chat_session.send_message(message.text)
            response_text = response.candidates[0].content.parts[0].text

            question_history_part = {
                "role": "user",
                "parts": [
                message.text,
                ],
            }

            answer_history_part = {
                "role": "model",
                "parts": [
                response_text
                ]
            }
            user.history.append(question_history_part)
            user.history.append(answer_history_part)

            while len(user.history) > user.memory_deep:
                user.history.pop(0)

            return response_text
        except Exception as e:
            Debug.log_error(f"CORE ERROR: {str(e)}")
            return "Error"
    @staticmethod
    def make_request_to_gas(bot,markup,user,message,system_instruct,gas_url)->bool:
        "Отправляет запрос в Google Apps Script, чтобы избежать проблем с региональными ограничениями"
        try:
            response_text=CORE.get_response_gas(user,message,system_instruct,gas_url)
            if response_text=="Error":
                return False
            parts = [response_text[i:i+4000] for i in range(0, len(response_text), 4000)]
            for i in parts[:-1]:
                bot.send_message(chat_id=message.chat.id, message_thread_id = message.message_thread_id, text = i)
            bot.send_message(chat_id=message.chat.id, message_thread_id = message.message_thread_id, text = parts[-1], reply_markup=markup)
            return True
        except Exception as e:
            Debug.log_error(f"CORE ERROR: {str(e)}")
            return False
    @staticmethod
    def cli_make_request_to_gas(user,message,system_instruct,gas_url)->bool:
        "Отправляет запрос в Google Apps Script, чтобы избежать проблем с региональными ограничениями. Выводит результат в консоль"
        try:
            response_text=CORE.get_response_gas(user,message,system_instruct,gas_url)
            if response_text=="Error":
                return False
            print(f"AI > \n    {response_text}")
            return True
        except Exception as e:
            Debug.log_error(f"CORE ERROR: {str(e)}")
            return False
    @staticmethod
    def get_response_gas(user,message,system_instruct,gas_url)->str:
        "Отправляет запрос в Google Apps Script, чтобы избежать проблем с региональными ограничениями. Возвращает ответ в виде строки; в случае ошибк вернет Error"
        try:
            data = {"parameter": f"SYSTEM_INSTRUCTION={system_instruct},\nHISTORY: {str(user.history)},\nUSER_MESSAGE: {message.text}"}  # Создаем словарь с данными для отправки
            response = requests.post(gas_url, data=data)  # Отправляем POST запрос

            question_history_part = {
            "role": "user",
            "parts": [
                message.text,
            ],
            }

            answer_history_part = {
            "role": "model",
            "parts": [
                response.text
            ]
            }
            user.history.append(question_history_part)
            user.history.append(answer_history_part)

            while len(user.history) > user.memory_deep:
                user.history.pop(0)
            print("a")
            return response.text
        except Exception as e:
            Debug.log_error(f"CORE ERROR: {str(e)}")
            return "Error"
    @staticmethod
    def get_setting(key):
        "Возвращает строку значения настройки по ключу key"
        try:
            with open("./bot_settings/bot_settings.txt", "r") as f:
                data = f.read().split("\n")
                for variable_string in data:
                    variable_pair = variable_string.split("=",1)
                    if variable_pair[0] == key:
                        return variable_pair[1]
        except Exception as e:
            Debug.log_warning(str(e))
    @staticmethod
    def set_setting(key, value):
        "Устанавливает строку значения настройки по ключу key"
        new_lines = []
        with open("./bot_settings/bot_settings.txt", "r") as f:
            new_lines = []
            data = f.read()
            lines = data.split("\n")
            for l in lines:
                pair = l.split("=")
                if pair[0] == key:
                    new_lines.append(f"{key}={value}")
                else:
                    new_lines.append(l)
        with open("./bot_settings/bot_settings.txt", "w") as f:
                f.write("\n".join(new_lines))
    @staticmethod
    def get_persona(code_name):
        "Возвращает строку с персоной нейросети"
        system_instruct = ""
        if os.path.isfile(f"bot_settings/Personas/{code_name}.txt"):
            with open(f"bot_settings/Personas/{code_name}.txt", "r") as f:
                data = f.read()
                if data == "":
                    system_instruct = f"You a bot named {code_name} with [blank] settings!"
                    Debug.log_error(f"No persona settings for this bot: [{code_name}]")
                else:
                    system_instruct = data
        else:
            with open(f"bot_settings/Personas/{code_name}.txt", "w") as f:
                f.write("")
                system_instruct = f"You a bot named {code_name} with [blank] settings!"
        return system_instruct
    @staticmethod
    def make_diagnostics():
        "проверяет есть ли нужные библиотеки и устанавливает в настроках нужные флаги"
        try:
            import google.generativeai
            CORE.set_setting("can_run_gemini","True")
        except Exception as e:
            CORE.set_setting("can_run_gemini","False")
        try:
            import telebot
            CORE.set_setting("can_run_telebot","True")
        except Exception as e:
            CORE.set_setting("can_run_telebot","False")
use_debug_log=CORE.get_setting("use_debug_log")=="True"
class Debug:
    "Класс, отвечающий за функции логирования"
    @staticmethod
    def log(msg:str):
        if not use_debug_log: return
        print(f"{msg}")
    @staticmethod    
    def log_warning(msg:str):
        if not use_debug_log: return
        print(f"{Colors.yellow}{msg}{Colors.blank}")
    @staticmethod
    def log_error(msg:str):
        if not use_debug_log: return
        print(f"{Colors.red}{msg}{Colors.blank}")
    @staticmethod
    def log_green(msg:str):
        if not use_debug_log: return
        print(f"{Colors.green}{msg}{Colors.blank}")
