import os
import telebot
import json
from telebot import types
import time
import threading
from CORE import CORE,Debug # обязательно импортируете эти классы для использования основных методов

#создаете переменные для работы
can_run_gemini = False # если нужно реализовать разные нейросети при наличии их большого количества, то можно импортировать библиотеки только при условии что вы можете ее запустить после диагностики.
host_name = "" # если у вас несколько разных хостов с запуском бота и вы хотите получать информацию о текущем, имеет смысл создать такую переменную
telegram_bot_api_key = "" # для создания самого бота в случае работы с телеграмом
gemini_api_key = "" # для использования и конфигурации genai
gas_url = "" # если вы хотите использовать обход ограничений по стране, вы всегда можете прийти к трюку с GoogleAppsScript
version = "" # всегда хочется знать текущую версию, просто для красоты
code_name = "Gemini" # кодовое имя вашего детища, по нему загружается персона и создаются подпапки с данными для пользователей
gemini_api_key_group = "public" # префикс по правилу префикс_gemini_api_key в bot_settings для разграничения разных api для разных ботов.
system_instruct = "" # полезно хранить системную инструкцию, если вы хотите иметь у бота некую "персону" другими словами личность

quoteTime=1200 # в секундах. в данном примере используется для того, чтобы указать, через какое время после достижения лимита на сообщения, он будет сброшен
message_limit = 10 # собственно сам лимит сообщения на пользователя, примечание: в этой версии он задается для пользователя только при создании, дальше при изменении этого значения у старых пользователей не изменится лимит. Зато вы всегда можете через текстовые редакторы вытсавить нужные значения.

# полезно задать админов, доверенных и забаненных пользователей для вашего бота, меняя в коде поведение скрипта при запросе от них, например в этом примере запросы от всех, кто находится в trusted будут обрабатываться без лимита на сообщения.
admins = []  
trusted = []
banned = []

geminiTASKS=[] # этот скрипт реализует конвейерную обработку запросов для удаления неточностей из-за асинхронности обработки запросов, поэтому мы используем некий массив задач

def get_settings():
    "Реализует загрузку переменных из файла bot_settings.txt"
    global can_run_gemini, telegram_bot_api_key, gemini_api_key, gas_url, host_name, version, system_instruct
    can_run_gemini = CORE.get_setting("can_run_gemini")=="True"
    telegram_bot_api_key = CORE.get_setting(f"{code_name}_tba")
    gemini_api_key = CORE.get_setting(f"{gemini_api_key_group}_gemini_api_key")
    gas_url = CORE.get_setting("gas_url")
    host_name = CORE.get_setting("host_name")
    version = CORE.get_setting(f"{code_name}_version")
    system_instruct=CORE.get_persona(code_name)

get_settings() # здесь мы загружаем настройки нашего бота, важно это сделать до начала их использования в коде

# если мы действительно можем запустить некую требующую билиотек функциональную составляющую нашей программы, то подключаем нужные библиотеки
if can_run_gemini:
    import google.generativeai as genai
    from google.generativeai.types import HarmCategory, HarmBlockThreshold

bot = telebot.TeleBot(telegram_bot_api_key) 
# создаем нашего бота, в данном случае telebot для работы с телеграммом, в случае работы с другими, вам нужно будет реализовать такой функционал:
# - получение сообщения от пользователя
# - индентификация пользователя по этому сообщению
# - возможность отправки ответа нужному пользователю
# если все эти возможности имеются, то можно переписать функции в этом коде, имеющие над собой что-либо начинающееся с @bot так, чтобы они использовали функционал вашего вендора бота.
class User:
    "Класс, в котором мы будем хранить все значения для одного пользователя"
    def __init__(self, current_screen, memory_deep, name, model, history, hour_quote, used_quote_messages,quote_reached_time):
        self.current_screen=current_screen
        self.memory_deep=memory_deep
        self.name=name
        self.model=model
        self.history=history
        self.hour_quote=hour_quote
        self.used_quote_messages=used_quote_messages
        self.quote_reached_time=quote_reached_time
class GeminiTask:
    "Класс, который мы используем для конвейера задач"
    def __init__(self, user, message):
        self.user = user
        self.message = message

# данные 2 функции нужны для работы сброса ограничений по квоте в условный промежуток времени
def get_current_time():
    """
    Функция возвращает текущее время в секундах
    """
    last_check_time = int(time.time())
    return last_check_time
def check_time_elapsed(last_check_time):
    """
    Возвращает прошедшее с last_checked_time время в секундах
    """
    current_time = int(time.time())
    elapsed = current_time - last_check_time
    return elapsed
def create_gemini_task(user, message):
    """
    Создает задачу в основном списке для конвейера
    """
    global geminiTASKS
    task = GeminiTask(user,message)
    geminiTASKS.append(task)
    user.used_quote_messages+=1
    if user.used_quote_messages>=user.hour_quote:
        user.quote_reached_time = get_current_time()
def polling_function():
    """
    Циклично проверяет наличие новых сообщений для бота
    """
    try:
        bot.polling(none_stop=True, timeout=10)
    except Exception as e:
        Debug.log_error(f"Произошла ошибка при polling: {e}")
def check_rights(user_id):
    """
    Проверяет, не забанен липользователь
    """
    if user_id in banned:
        return False
    else:
        return True
#Вам нужна функция, с которой вы будете стартовать, то есть реализуете некий функционал, который будет выполняться при запуске скрипта, запустите второстепенные потоки
def sys_start():
    """
    Отвечает за запуск системы и всех потоков
    """
    global bot
    try:
        Debug.log("System starts...")
        # например здесь мы отсылаем админам параметры запуска
        if CORE.get_setting("send_start_info_to_admins")=="True":
            Debug.log("Sending start info to admins")
            crash_data = ""
            if os.path.isfile(f"{code_name}_crash.txt"):
                with open(f"{code_name}_crash.txt", "r") as f:
                    crash_data = f.read()
                os.system(f"rm {code_name}_crash.txt")
            if crash_data != "":
                crash_data = "\nCrashed due to: "+crash_data
            for admin_id in admins:
                bot.send_message(admin_id, f"Server starting with:\n - host: {host_name}\n - can_run_gemini: {can_run_gemini}\n{crash_data}")
            Debug.log_green("Done")

        # запускаем в отдельном потоке чек сообщений ботом
        Debug.log("Enabling bot polling...")
        polling_thread = threading.Thread(target=polling_function)
        polling_thread.daemon = True  # Завершаем поток при завершении основной программы
        polling_thread.start()
        Debug.log("Done")

        # что-нибудь доконфигурируем
        if can_run_gemini:
            Debug.log("Gemini configure...")
            genai.configure(api_key=gemini_api_key)
            Debug.log_green("Done")

        Debug.log("Loading banned list")
        load_banned_list()
        Debug.log_green("Done")
        

    except Exception as e:
        Debug.log_error(code_name, [f"Error in sys_start(): {e}"])
def save_user(user_id, user):
    """
    Сохраняет пользователя 
    """
    try:
        if not os.path.isdir(f"Database/{user_id}/"):
            Debug.log_warning(f"No directory for user: {user_id} -> Creating new folder")
            os.system(f"mkdir Database/{user_id}")
        if not os.path.isdir(f"Database/{user_id}/{code_name}/"):
            Debug.log_warning(f"No [{code_name}] sub-directory for user: {user_id} -> Creating new folder")
            os.system(f"mkdir Database/{user_id}/{code_name}")
        if not os.path.isfile(f"Database/{user_id}/{code_name}/memory.txt"):
            Debug.log_warning(f"No history log for user: {user_id} -> loading [DEFAULT] history")
        with open(f"Database/{user_id}/{code_name}/memory.txt", "w") as f:
            json.dump(user.history,f, ensure_ascii=False, indent=2)
            Debug.log(f"History for [{user_id}] saved")
        with open(f"Database/{user_id}/{code_name}/data.txt", "w") as f:
            f.write(f"{user.current_screen}\n{user.memory_deep}\n{user.name}\n{user.model}\n{user.hour_quote}\n{user.used_quote_messages}\n{user.quote_reached_time}")

    except Exception as e:
        Debug.log_error(code_name, [f"Error in save_user: {e}"])
def load_user(user_id):
    """
    Загружает пользователя
    """
    user = User("MANAGER", 10, "User", "models/gemini-2.0-flash-exp",[], message_limit, 0,0)
    try:
        if not os.path.isdir(f"Database/{user_id}/"):
            Debug.log_warning(f"No directory for user: {user_id} -> Creating new folder")
            os.system(f"mkdir Database/{user_id}")
        if not os.path.isdir(f"Database/{user_id}/{code_name}/"):
            Debug.log_warning(f"No [{code_name}] sub-directory for user: {user_id} -> Creating new folder")
            os.system(f"mkdir Database/{user_id}/{code_name}")
        if not os.path.isfile(f"Database/{user_id}/{code_name}/memory.txt"):
            Debug.log_warning(f"No history log for user: {user_id} -> loading [DEFAULT] history")
            with open(f"Database/{user_id}/{code_name}/memory.txt", "w") as f:
                f.write("[]")
        if True:
            with open(f"Database/{user_id}/{code_name}/memory.txt", "r") as f:
                user.history = json.load(f)
                Debug.log(f"History for [{user_id}] loaded")
            if not os.path.isfile(f"Database/{user_id}/{code_name}/data.txt"):
                Debug.log_warning(f"No data.txt for user: {user_id} -> loading [DEFAULT] data")
            else:
                with open(f"Database/{user_id}/{code_name}/data.txt", "r") as b:
                    data = b.read().split("\n")
                    user.current_screen=data[0]
                    user.memory_deep=int(data[1])
                    user.name=data[2]
                    user.model=data[3]
                    user.hour_quote=int(data[4])
                    user.used_quote_messages=int(data[5])
                    user.quote_reached_time=int(data[6])
    except Exception as e:
        Debug.log_error(code_name, [f"Error in load_user: {e}"])
    return user
def send_message_to_gemini_gas(user, message):
    "Отправляет запрос в Google Apps Script, чтобы избежать проблем с региональными ограничениями."
    try:
        markup = types.InlineKeyboardMarkup()
        button1 = types.InlineKeyboardButton(f"В меню", callback_data=f"current_screen>MANAGER")
        markup.add(button1)
        return CORE.make_request_to_gas(bot=bot,markup=markup,user=user,message=message,system_instruct=system_instruct,gas_url=gas_url)
    except Exception as e:
        return False
def send_message_to_gemini(user,message):
    """
    Отправляет запрос через google.generativeai и при неудаче отправляет через Google Apps Script для обхода региональных ограничений
    """
    if not send_message_to_gemini_genai(user,message):
        send_message_to_gemini_gas(user,message)
    save_user(message.from_user.id, user)
def send_message_to_gemini_genai(user, message):
    """
    Отправляет запрос gemini напрямую через google.generativeai api
    """
    if not can_run_gemini:
        return False
    try:
        
        generation_config = {
          "temperature": 1,
          "top_p": 0.95,
          "top_k": 40,
          "max_output_tokens": 8192,
          "response_mime_type": "text/plain",
        }
        model = genai.GenerativeModel(
            model_name=user.model,
            generation_config=generation_config,
            system_instruction=system_instruct,
            safety_settings={
                        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
            }
        )

        markup = types.InlineKeyboardMarkup()
        button1 = types.InlineKeyboardButton(f"В меню", callback_data=f"current_screen>MANAGER")
        markup.add(button1)
        return CORE.make_request_to_genai(bot=bot,markup=markup,user=user,message=message,model=model)
    except Exception as e:
        Debug.log_error(code_name, f"Error in send_message_to_gemini_genai(): {e}")
        return False
def load_banned_list():
    """
    Загружает список заблокированных пользователей
    """
    global banned
    with open("bot_settings/banned_users.txt", "r") as f:
        banned = list(map(int,f.read().split("\n")[:-1]))
def process_message(user, message):
    """
    Решает что сделать исходя из сообщения пользователя
    """
    msg = message.text
    if user.current_screen == "MEMORY_SET":
        try:
            nd = int(msg)
            if nd < 2:
                bot.send_message(message.from_user.id, f"Введите число >=2!")
            else:
                user.memory_deep = nd
                markup = types.InlineKeyboardMarkup()
                button0 = types.InlineKeyboardButton(f"Ок", callback_data=f"current_screen>MEMORY")
                markup.add(button0)
                bot.send_message(message.from_user.id, f"Глубина памяти установлена на [{user.memory_deep}]",  reply_markup=markup)
        except Exception as e:
            Debug.log_error(code_name, [f"Error in MEMORY_SET: {e}"])
            bot.send_message(message.from_user.id, f"Введите число >=2!")
    else:
        if(user.used_quote_messages<user.hour_quote or message.from_user.id in trusted):
            create_gemini_task(user, message)
        else:
            t = check_time_elapsed(user.quote_reached_time)
            if(t>=quoteTime):
                print("a")
                user.used_quote_messages = 0
                create_gemini_task(user, message)
            else:
                bot.send_message(message.from_user.id, f"Вы достигли лимита на сообщения в час, подождите еще {quoteTime-t} секунд")
    #save_user(message.from_user.id, user)

@bot.message_handler(commands=['info'])
def show_user_info(message):
    if not check_rights(message.from_user.id):
        return
    user = load_user(message.from_user.id)
    bot.send_message(message.from_user.id, f"{user.used_quote_messages}/{user.hour_quote} -> [{quoteTime-check_time_elapsed(user.quote_reached_time)}]")
@bot.message_handler(commands=['menu','start'])
def show_menu(message):
    if not check_rights(message.from_user.id):
        return
    user = load_user(message.from_user.id)
    markup = types.InlineKeyboardMarkup()
    button1 = types.InlineKeyboardButton(f"Нейросеть", callback_data=f"current_screen>AI_SETTINGS")
    markup.add(button1)
    user.current_screen = "MANAGER"
    bot.send_message(message.from_user.id, f"{code_name}, version: [{version}]", reply_markup=markup)
@bot.message_handler(content_types=['text'])
def get_text_message(message):
    if not check_rights(message.from_user.id):
        return
    #Debug.log([f"Get message from user [{message.from_user.id}]", message.text])
    user = load_user(message.from_user.id)
    process_message(user, message)
@bot.callback_query_handler(func=lambda call: True)
def answer(call):
    if call.from_user.id not in trusted:
        bot.send_message(call.from_user.id, f"Недостаточно прав!")
        return
    question = call.data
    user = load_user(call.from_user.id)
    Debug.log([f"Get call [{call.data}] from [{call.from_user.id}]"])
    if question.split(">")[0] == "current_screen":
        target_screen=question.split(">")[1]
        Debug.log([f"Change [{call.from_user.id}] current_screen from [{user.current_screen}] to [{target_screen}]"])
        user.current_screen=target_screen
        if target_screen == "MANAGER":
            markup = types.InlineKeyboardMarkup()
            button1 = types.InlineKeyboardButton(f"Нейросеть", callback_data=f"current_screen>AI_SETTINGS")
            markup.add(button1)
            bot.edit_message_text(f"{code_name}, version: [{version}]", call.from_user.id,call.message.id,reply_markup=markup)
        elif target_screen == "AI_SETTINGS":
            markup = types.InlineKeyboardMarkup()
            button0 = types.InlineKeyboardButton(f"Назад", callback_data=f"current_screen>MANAGER")
            markup.add(button0)
            button2 = types.InlineKeyboardButton(f"Работа с памятью", callback_data=f"current_screen>MEMORY")
            markup.add(button2)
            bot.edit_message_text("Настройки нейросети:", call.from_user.id,call.message.id,reply_markup=markup)
        elif target_screen == "SET_MODEL":
            markup = types.InlineKeyboardMarkup()
            button0 = types.InlineKeyboardButton(f"Назад", callback_data=f"current_screen>AI_SETTINGS")
            markup.add(button0)
            try:
                for m in genai.list_models():
                    b = types.InlineKeyboardButton(m.name, callback_data=f"SET->{m.name}")
                    markup.add(b)
                bot.edit_message_text(f"Текущая модель: {user.model}", call.from_user.id,call.message.id, reply_markup=markup)
            except Exception as e:
                Debug.log_error(code_name, [f"Err in SET_MODEL: {e}"])
        elif target_screen == "MEMORY":
            markup = types.InlineKeyboardMarkup()
            button0 = types.InlineKeyboardButton(f"Назад", callback_data=f"current_screen>AI_SETTINGS")
            markup.add(button0)
            button1 = types.InlineKeyboardButton(f"Установить глубину памяти", callback_data=f"current_screen>MEMORY_SET")
            markup.add(button1)
            button3 = types.InlineKeyboardButton(f"Очистить память", callback_data=f"current_screen>MEMORY_CLEAR")
            markup.add(button3)
            bot.edit_message_text(f"Память: {len(user.history)}/{user.memory_deep}", call.from_user.id,call.message.id, reply_markup=markup)
        elif target_screen == "MEMORY_SHOW":
            markup = types.InlineKeyboardMarkup()
            button0 = types.InlineKeyboardButton(f"Назад", callback_data=f"current_screen>MEMORY")
            markup.add(button0)
            parts = [user.history[i:i+4000] for i in range(0, len(user.history), 4000)]
            for p in parts:
                bot.send_message(chat_id=call.chat.id, message_thread_id = call.message_thread_id, text = p, reply_markup=markup)
        elif target_screen == "MEMORY_SET":
            markup = types.InlineKeyboardMarkup()
            button0 = types.InlineKeyboardButton(f"Назад", callback_data=f"current_screen>MEMORY")
            markup.add(button0)
            bot.edit_message_text(f"Введите глубину памяти (не меньше 2)", call.from_user.id,call.message.id, reply_markup=markup)
        elif target_screen == "MEMORY_CLEAR":
            user.history = []
            markup = types.InlineKeyboardMarkup()
            button0 = types.InlineKeyboardButton(f"Назад", callback_data=f"current_screen>MEMORY")
            markup.add(button0)
            bot.edit_message_text(f"Память очищена", call.from_user.id,call.message.id, reply_markup=markup)
    elif question[0] == "S":
        user.model = question[5:]
        markup = types.InlineKeyboardMarkup()
        button0 = types.InlineKeyboardButton(f"Назад", callback_data=f"current_screen>AI_SETTINGS")
        markup.add(button0)
        bot.edit_message_text(f"Текущая модель: {user.model}", call.from_user.id,call.message.id, reply_markup=markup)

    save_user(call.from_user.id, user)

sys_start()
while True:
    if len(geminiTASKS) > 0:
        send_message_to_gemini(geminiTASKS[0].user, geminiTASKS[0].message)
        del geminiTASKS[0]
