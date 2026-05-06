import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import os
import json
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ========== НАСТРОЙКИ ==========
TOKEN = os.environ.get("VK_TOKEN")
GROUP_ID = 209797699
SUPER_ADMIN = 585368555

# ========== ДЕФОЛТЫ ==========
DEFAULT_BALANCE = 250
DEFAULT_CRYSTALS = 0
DEFAULT_ANIMAL_LIMIT = 5

# ========== ЗАЩИТА ОТ ДУБЛЕЙ ==========
last_sent = {}
SEND_COOLDOWN = 1.5

# Создаём клавиатуру один раз, чтобы не делать это при каждом сообщении
MAIN_KEYBOARD = VkKeyboard(one_time=False)
MAIN_KEYBOARD.add_button('💰 Баланс', color=VkKeyboardColor.PRIMARY)
MAIN_KEYBOARD.add_button('🎒 Ресурсы', color=VkKeyboardColor.POSITIVE)
MAIN_KEYBOARD.add_line()  # Перенос на новую строку
MAIN_KEYBOARD.add_button('🛍️ Магазин', color=VkKeyboardColor.SECONDARY)
MAIN_KEYBOARD.add_button('🤔 Помощь', color=VkKeyboardColor.SECONDARY)

def safe_send(vk, user_id, message, keyboard=True):
    """Отправляет сообщение. Если keyboard=True, прикрепляет главное меню."""
    now = time.time()
    key = (user_id, message)
    if key in last_sent and (now - last_sent[key]) < SEND_COOLDOWN:
        return
    last_sent[key] = now
    if len(last_sent) > 300:
        last_sent.clear()
    
    # Собираем параметры для отправки
    params = {
        'user_id': user_id,
        'message': message,
        'random_id': 0
    }
    # Если это не специальное сообщение, добавляем клавиатуру
    if keyboard:
        params['keyboard'] = MAIN_KEYBOARD.get_keyboard()
    
    vk.messages.send(**params)
    
# ========== GOOGLE SHEETS ==========
def get_sheet():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    creds_dict = json.loads(creds_json)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1aKYfYOGk4hKNdwbP6dLDwJrDJbdzPrr1fNsNg6-XD4Y")
    return sheet

def add_to_bank(currency_type, amount):
    if amount <= 0:
        return
    sheet = get_sheet()
    ws = sheet.worksheet("Банк")
    if currency_type == "монеты":
        current = int(ws.cell(2, 2).value or 0)
        ws.update_cell(2, 2, current + amount)
    elif currency_type == "кристаллы":
        current = int(ws.cell(3, 2).value or 0)
        ws.update_cell(3, 2, current + amount)

def get_admins():
    try:
        sheet = get_sheet()
        ws = sheet.worksheet("Админы")
        ids = ws.col_values(1)[1:]
        admins = [int(x) for x in ids if x.strip().isdigit()]
    except:
        admins = []
    if SUPER_ADMIN not in admins:
        admins.append(SUPER_ADMIN)
    return admins

# ========== БАЛАНС ==========
def get_user_row(user_id):
    sheet = get_sheet()
    ws = sheet.worksheet("Баланс")
    try:
        cell = ws.find(str(user_id))
        row = cell.row
        if not ws.cell(row, 4).value:
            ws.update_cell(row, 4, DEFAULT_CRYSTALS)
        if not ws.cell(row, 5).value:
            ws.update_cell(row, 5, DEFAULT_ANIMAL_LIMIT)
        if not ws.cell(row, 2).value:
            try:
                vk_session = vk_api.VkApi(token=TOKEN)
                vk = vk_session.get_api()
                user_info = vk.users.get(user_ids=user_id)[0]
                name = f"{user_info['first_name']} {user_info['last_name']}"
                ws.update_cell(row, 2, name)
            except:
                pass
        return row
    except:
        name = ""
        try:
            vk_session = vk_api.VkApi(token=TOKEN)
            vk = vk_session.get_api()
            user_info = vk.users.get(user_ids=user_id)[0]
            name = f"{user_info['first_name']} {user_info['last_name']}"
        except:
            pass
        ws.append_row([str(user_id), name, DEFAULT_BALANCE, DEFAULT_CRYSTALS, DEFAULT_ANIMAL_LIMIT, ""])
        cell = ws.find(str(user_id))
        return cell.row

def get_balance(user_id):
    row = get_user_row(user_id)
    return int(get_sheet().worksheet("Баланс").cell(row, 3).value)

def get_crystals(user_id):
    row = get_user_row(user_id)
    return int(get_sheet().worksheet("Баланс").cell(row, 4).value)

def get_animal_limit(user_id):
    row = get_user_row(user_id)
    return int(get_sheet().worksheet("Баланс").cell(row, 5).value)

def add_balance(user_id, amount):
    sheet = get_sheet()
    ws = sheet.worksheet("Баланс")
    row = get_user_row(user_id)
    new_val = int(ws.cell(row, 3).value) + amount
    ws.update_cell(row, 3, new_val)

def add_crystals(user_id, amount):
    sheet = get_sheet()
    ws = sheet.worksheet("Баланс")
    row = get_user_row(user_id)
    new_val = int(ws.cell(row, 4).value) + amount
    ws.update_cell(row, 4, new_val)

def set_animal_limit(user_id, new_limit):
    sheet = get_sheet()
    ws = sheet.worksheet("Баланс")
    row = get_user_row(user_id)
    ws.update_cell(row, 5, new_limit)

# ========== МАГАЗИН ==========
SHOP_ITEMS = {
    "походы": {
        "name": "🏕️ Для походов",
        "items": [
            {"name": "Карта местности", "price": 120, "crystals": 0, "desc": "шанс +20% на редкий ресурс",
             "keywords": ["карта", "карта местности", "местность"]},
            {"name": "Фонарик", "price": 150, "crystals": 0, "desc": "+1 предмет к добыче",
             "keywords": ["фонарик", "фонарь", "фанарик", "фон"]},
            {"name": "Портал возврата", "price": 250, "crystals": 1, "desc": "мгновенное возвращение",
             "keywords": ["портал", "портал возврата", "возврат"]},
            {"name": "Компас удачи", "price": 100, "crystals": 0, "desc": "+50% монет в походе",
             "keywords": ["компас", "компас удачи", "удача"]},
            {"name": "Эликсир опыта", "price": 130, "crystals": 0, "desc": "+30% к опыту",
             "keywords": ["эликсир", "эликсир опыта", "опыт"]},
        ]
    },
    "пары": {
        "name": "💞 Для создания пары",
        "items": [
            {"name": "Букет цветов", "price": 110, "crystals": 0, "desc": "+25% к отношениям",
             "keywords": ["букет", "букет цветов", "цветы"]},
            {"name": "Праздничный ужин", "price": 200, "crystals": 0, "desc": "+50% к отношениям",
             "keywords": ["ужин", "праздничный ужин", "праздничный"]},
            {"name": "Духи со сладким ароматом", "price": 290, "crystals": 0, "desc": "+75% к отношениям",
             "keywords": ["духи", "аромат", "сладкий аромат"]},
            {"name": "Свеча единения", "price": 80, "crystals": 0, "desc": "не поссорятся при встрече",
             "keywords": ["свеча", "свеча единения", "единение"]},
            {"name": "Парный амулет", "price": 180, "crystals": 0, "desc": "+40% к шансу пары",
             "keywords": ["амулет", "парный амулет", "парный"]},
            {"name": "Лунный нектар", "price": 450, "crystals": 1, "desc": "симпатия у враждующих",
             "keywords": ["нектар", "лунный нектар", "лунный"]},
        ]
    },
    "лечение": {
        "name": "💊 Лечение и уход",
        "items": [
            {"name": "Ножницы для когтей", "price": 200, "crystals": 0, "desc": "многоразовые",
             "keywords": ["когти", "ножницы для когтей", "ногти"]},
            {"name": "Ножницы для стрижки", "price": 100, "crystals": 0, "desc": "многоразовые",
             "keywords": ["стрижка", "ножницы для стрижки", "стричь"]},
            {"name": "Расчёска от пухоедов", "price": 300, "crystals": 0, "desc": "многоразовая",
             "keywords": ["расчёска", "расческа", "пухоеды", "пухоед"]},
            {"name": "Шампунь от пухоедов", "price": 40, "crystals": 0, "desc": "одноразовый",
             "keywords": ["шампунь", "шампун"]},
            {"name": "Мазь от ран", "price": 50, "crystals": 0, "desc": "лечит царапины",
             "keywords": ["мазь", "мазь от ран", "раны", "рана"]},
            {"name": "Костыль", "price": 120, "crystals": 0, "desc": "снимает ограничения на 1 день",
             "keywords": ["костыль", "костыли"]},
            {"name": "Лечение перелома", "price": 350, "crystals": 0, "desc": "восстановление костей",
             "keywords": ["перелом", "лечение перелома", "кости"]},
            {"name": "Лечение сотрясения", "price": 450, "crystals": 0, "desc": "компресс и покой",
             "keywords": ["сотрясение", "лечение сотрясения", "мозг"]},
            {"name": "Лечение тяжёлых болезней", "price": 500, "crystals": 0, "desc": "опухоль, грыжа, тромб",
             "keywords": ["болезнь", "тяжёлая болезнь", "опухоль", "грыжа", "тромб"]},
            {"name": "Эликсир бодрости", "price": 180, "crystals": 0, "desc": "второй поход за день",
             "keywords": ["бодрость", "эликсир бодрости", "бодрый"]},
        ]
    },
    "малыши": {
        "name": "🍼 Для беременных и малышей",
        "items": [
            {"name": "Лакомства для мамы", "price": 120, "crystals": 0, "desc": "+25% к шансу родов",
             "keywords": ["лакомства", "лакомство", "для мамы", "мама"]},
            {"name": "Мягкая лежанка", "price": 350, "crystals": 0, "desc": "+60% к шансу родов",
             "keywords": ["лежанка", "мягкая лежанка", "лежак"]},
            {"name": "Витамины", "price": 170, "crystals": 0, "desc": "+30% к шансу родов",
             "keywords": ["витамины", "витаминки", "витамин"]},
            {"name": "Ускоритель родов", "price": 300, "crystals": 1, "desc": "мгновенные роды",
             "keywords": ["ускоритель", "роды", "ускоритель родов"]},
            {"name": "Детское питание", "price": 80, "crystals": 0, "desc": "ускоряет рост на 1 день",
             "keywords": ["питание", "детское питание", "детский"]},
            {"name": "Колыбелька", "price": 400, "crystals": 0, "desc": "растить малыша в доме",
             "keywords": ["колыбель", "колыбелька", "люлька"]},
        ]
    },
    "редкие": {
        "name": "✨ Редкие и магические",
        "items": [
            {"name": "Камень возрождения", "price": 800, "crystals": 3, "desc": "воскрешает зверя",
             "keywords": ["камень", "возрождение", "воскрешение", "воскрес"]},
            {"name": "Амулет удачи", "price": 180, "crystals": 0, "desc": "гарантированное Золото",
             "keywords": ["амулет", "удача", "амулет удачи"]},
            {"name": "Кристальная карта", "price": 350, "crystals": 0, "desc": "доступ в любую локацию",
             "keywords": ["карта", "кристальная", "кристальная карта"]},
        ]
    },
}

SHOP_CATEGORIES = {
    "1": "походы",
    "2": "пары",
    "3": "лечение",
    "4": "малыши",
    "5": "редкие",
}

shop_state = {}

# ========== ПОИСК ТОВАРА ==========
def find_item(query):
    """Ищет товар по ключевым словам во всех категориях. Возвращает (item, category_key) или (None, None)."""
    query = query.lower().strip()
    best_match = None
    best_cat = None
    
    for cat_key, cat in SHOP_ITEMS.items():
        for item in cat["items"]:
            for kw in item["keywords"]:
                if kw in query or query in kw:
                    # Чем длиннее совпадение, тем лучше
                    if best_match is None or len(kw) > len(best_match[0]):
                        best_match = (kw, item)
                        best_cat = cat_key
    
    if best_match:
        return best_match[1], best_cat
    return None, None

# ========== ПРОМОКОДЫ ==========
def check_promo(code, user_id):
    sheet = get_sheet()
    ws = sheet.get_worksheet_by_id(1075907631)
    all_codes = ws.col_values(1)
    
    found_row = None
    for i, stored_code in enumerate(all_codes):
        if i == 0:
            continue
        if stored_code.strip().lower() == code.strip().lower():
            found_row = i + 1
            break
    
    if found_row is None:
        return None, f"❌ Код «{code}» не найден"
    
    # Проверяем количество использований (столбец C = uses)
    uses_left = ws.cell(found_row, 3).value
    if uses_left:
        uses_left = int(uses_left)
        if uses_left <= 0:
            return None, f"❌ Промокод «{code}» больше недействителен"
    else:
        uses_left = None  # Бесконечный
    
    # Проверяем, не использовал ли уже этот игрок этот код
    balance_ws = sheet.worksheet("Баланс")
    try:
        user_cell = balance_ws.find(str(user_id))
        used_promos = balance_ws.cell(user_cell.row, 6).value or ""
        if code.strip().lower() in used_promos.lower():
            return None, "❌ Ты уже активировал этот промокод!"
    except:
        pass
    
    try:
        reward_text = ws.cell(found_row, 2).value
        if not reward_text:
            return None, "❌ Пустая награда"
        
        reward = json.loads(reward_text.strip())
        
        # Записываем код в used_promos игрока
        try:
            new_used = (used_promos + "," + code.strip()) if used_promos else code.strip()
            balance_ws.update_cell(user_cell.row, 6, new_used)
        except:
            row = get_user_row(user_id)
            balance_ws.update_cell(row, 6, code.strip())
        
        # Уменьшаем количество использований
        if uses_left is not None:
            uses_left -= 1
            ws.update_cell(found_row, 3, uses_left)
            # Автоматически обновляем статус в столбце D (Статус)
            if uses_left > 0:
                ws.update_cell(found_row, 4, f"✅ Активен ({uses_left} исп.)")
            else:
                ws.update_cell(found_row, 4, "❌ Исчерпан")
        else:
            # Бесконечный
            ws.update_cell(found_row, 4, "✅ Бесконечный")
        
        return reward, None
    except Exception as e:
        return None, f"❌ Ошибка чтения награды: {e}"

# ========== РЕСУРСЫ ==========
def get_resources(user_id):
    sheet = get_sheet()
    ws = sheet.worksheet("Ресурсы")
    try:
        cell = ws.find(str(user_id))
        return json.loads(ws.cell(cell.row, 2).value)
    except:
        ws.append_row([str(user_id), "{}"])
        return {}

def add_resource(user_id, resource_name, amount):
    sheet = get_sheet()
    ws = sheet.worksheet("Ресурсы")
    try:
        cell = ws.find(str(user_id))
        resources = json.loads(ws.cell(cell.row, 2).value)
        resources[resource_name] = resources.get(resource_name, 0) + amount
        ws.update_cell(cell.row, 2, json.dumps(resources, ensure_ascii=False))
    except:
        ws.append_row([str(user_id), json.dumps({resource_name: amount}, ensure_ascii=False)])

ALL_RESOURCES = [
    "💐🌸🌺 Цветы", "🍓 Ягоды", "🐁 Мыши", "🐦 Птицы",
    "🦷 Клыки змеи", "🏻 Твёрдая шкура", "🍄 Грибы",
    "🍯 Тёмный мёд", "🪨 Мшистый камень", "🌿 Папаротник-шептун",
    "🥜 Сонный орешек", "🌕 Лунный шёлк", "🍁 Золотой лист",
    "🦌 Рог оленя", "🕯️ Лесная свеча",
    "❄️ Искристый снег", "🍇 Морозные ягодки", "🐟 Серебряная рыбка",
    "🐚 Ракушка", "🦉 Перо полярной совы", "⭐ Замёрзшая звезда",
    "💧 Эфирная капля", "🕊️ Облачное пёрышко", "🏵️ Туманный цветок",
    "🌊 Сладкая пена", "🌟 Искра водопада", "🦋 Водяная бабочка",
    "🌙 Лунный блик", "💥 Звёздная пыльца",
    "🍎 Золотое яблоко", "🌰 Волшебный орех", "🕸️ Паутина",
    "📜 Свиток", "🔔 Колокольчик тишины", "☄️ Звездопадный камень",
    "🔸 Золото",
]

# ========== ОБРАБОТКА ==========
def handle_message(vk, event):
    user_id = event.obj.message['from_id']
    text = event.obj.message['text'].strip()
    lower_text = text.lower()                    # ← сначала эта строка
    lower_text = ''.join(c for c in lower_text if c.isalnum() or c.isspace()).strip()  # ← потом эта

    # --- АДМИН ---
    if lower_text == "админ":
        if user_id in get_admins():
            help_text = (
                "🔐 Админские команды:\n\n"
                "• Пополнить монеты СУММА ID\n"
                "• Пополнить кристаллы СУММА ID\n"
                "• Пополнить лимит ЧИСЛО ID\n"
                "• Пополнить ресурс НАЗВАНИЕ КОЛИЧЕСТВО ID"
            )
        else:
            help_text = "🤔 Неизвестная команда. Напиши «Помощь»."
        safe_send(vk, user_id, help_text)
        return

    # --- БАНК (для админов) ---
    if lower_text == "банк":
        if user_id in get_admins():
            sheet = get_sheet()
            ws = sheet.worksheet("Банк")
            coins = ws.cell(2, 2).value or 0
            crystals = ws.cell(3, 2).value or 0
            safe_send(vk, user_id, f"🏦 Банк игры:\n💰 Монеты: {coins}\n💎 Кристаллы: {crystals}")
        else:
            safe_send(vk, user_id, "🤔 Неизвестная команда.")
        return

    # --- МАГАЗИН ---
    if lower_text in ["магазин", "купить", "shop"]:
        balance = get_balance(user_id)
        crystals = get_crystals(user_id)
        message = (
            f"🛍️ Добро пожаловать в магазин!\n"
            f"💰 Твой баланс: {balance} монет, {crystals}💎\n\n"
            f"Выбери категорию:\n"
            f"1️⃣ Для походов\n"
            f"2️⃣ Для создания пары\n"
            f"3️⃣ Лечение и уход\n"
            f"4️⃣ Для беременных и малышей\n"
            f"5️⃣ Редкие и магические\n"
            f"0️⃣ Выйти\n\n"
            f"Или напиши название товара сразу (например: фонарик)"
        )
        shop_state[user_id] = {"step": "category"}
        safe_send(vk, user_id, message)
        return

    # --- БЫСТРАЯ ПОКУПКА (купить + название) ---
    if lower_text.startswith("купить "):
        query = lower_text.replace("купить ", "", 1).strip()
        # Отделяем количество, если есть (купить фонарик 2)
        qty = 1
        parts = query.split()
        if parts and parts[-1].isdigit():
            qty = int(parts[-1])
            query = " ".join(parts[:-1])
        
        item, cat_key = find_item(query)
        if item:
            total_price = item["price"] * qty
            total_crystals = item["crystals"] * qty
            balance = get_balance(user_id)
            crystals = get_crystals(user_id)
            
            if balance < total_price:
                safe_send(vk, user_id, f"❌ Не хватает монет!\nТвой баланс: {balance}💰\nНужно: {total_price}💰")
                return
            if crystals < total_crystals:
                safe_send(vk, user_id, f"❌ Не хватает кристаллов!\nУ тебя: {crystals}💎\nНужно: {total_crystals}💎")
                return
            
            add_balance(user_id, -total_price)
            if total_crystals > 0:
                add_crystals(user_id, -total_crystals)
            add_to_bank("монеты", total_price)
            if total_crystals > 0:
                add_to_bank("кристаллы", total_crystals)
            add_resource(user_id, f"🛍️ {item['name']}", qty)
            
            new_balance = get_balance(user_id)
            new_crystals = get_crystals(user_id)
            safe_send(vk, user_id, f"✅ Куплено: {item['name']} ({qty} шт.)\nПотрачено: {total_price}💰" + (f" + {total_crystals}💎" if total_crystals > 0 else "") + f"\n💰 Осталось: {new_balance} монет, {new_crystals}💎")
        else:
            safe_send(vk, user_id, "❌ Товар не найден. Напиши «Магазин» для списка.")
        return

    # --- ПОКУПКА ПО НАЗВАНИЮ В МАГАЗИНЕ ---
    if user_id in shop_state and shop_state[user_id]["step"] == "item":
        query = lower_text
        qty = 1
        # Отделяем количество (фонарик 2 или фонарик2)
        parts = query.split()
        if parts:
            # Проверяем, не число ли последний элемент
            if parts[-1].isdigit():
                qty = int(parts[-1])
                query = " ".join(parts[:-1])
            else:
                # Может быть склеено: фонарик2
                last_word = parts[-1]
                num_str = ""
                while last_word and last_word[-1].isdigit():
                    num_str = last_word[-1] + num_str
                    last_word = last_word[:-1]
                if num_str:
                    qty = int(num_str)
                    parts[-1] = last_word
                    query = " ".join(parts)
        
        item, cat_key = find_item(query)
        if item:
            total_price = item["price"] * qty
            total_crystals = item["crystals"] * qty
            balance = get_balance(user_id)
            crystals = get_crystals(user_id)
            
            if balance < total_price:
                safe_send(vk, user_id, f"❌ Не хватает монет!\nТвой баланс: {balance}💰\nНужно: {total_price}💰")
                return
            if crystals < total_crystals:
                safe_send(vk, user_id, f"❌ Не хватает кристаллов!\nУ тебя: {crystals}💎\nНужно: {total_crystals}💎")
                return
            
            add_balance(user_id, -total_price)
            if total_crystals > 0:
                add_crystals(user_id, -total_crystals)
            add_to_bank("монеты", total_price)
            if total_crystals > 0:
                add_to_bank("кристаллы", total_crystals)
            add_resource(user_id, f"🛍️ {item['name']}", qty)
            
            new_balance = get_balance(user_id)
            new_crystals = get_crystals(user_id)
            safe_send(vk, user_id, f"✅ Куплено: {item['name']} ({qty} шт.)\nПотрачено: {total_price}💰" + (f" + {total_crystals}💎" if total_crystals > 0 else "") + f"\n💰 Осталось: {new_balance} монет, {new_crystals}💎")
            del shop_state[user_id]
        else:
            safe_send(vk, user_id, "❌ Товар не найден. Напиши «0» чтобы вернуться к категориям.")
        return

    # Обработка шагов магазина (цифры)
    if user_id in shop_state:
        state = shop_state[user_id]
        
        if lower_text == "0" or lower_text == "выйти":
            del shop_state[user_id]
            safe_send(vk, user_id, "👋 Ты вышел из магазина.")
            return
        
        if state["step"] == "category":
            if lower_text in SHOP_CATEGORIES:
                cat_key = SHOP_CATEGORIES[lower_text]
                cat = SHOP_ITEMS[cat_key]
                shop_state[user_id] = {"step": "item", "category": cat_key}
                
                balance = get_balance(user_id)
                crystals = get_crystals(user_id)
                message = f"{cat['name']}\n💰 Твой баланс: {balance} монет, {crystals}💎\n\n"
                for i, item in enumerate(cat["items"], 1):
                    price_str = f"{item['price']}💰"
                    if item['crystals'] > 0:
                        price_str += f" + {item['crystals']}💎"
                    message += f"{i}. {item['name']} — {price_str}\n   {item['desc']}\n\n"
                message += "0. Назад\n\nНапиши название товара и количество (например: фонарик 2)"
                safe_send(vk, user_id, message)
            else:
                safe_send(vk, user_id, "❌ Неверный номер категории. Выбери от 1 до 5 или 0 для выхода.")
            return

    # --- БАЛАНС ---
    if lower_text == "баланс":
        balance = get_balance(user_id)
        crystals = get_crystals(user_id)
        animal_limit = get_animal_limit(user_id)
        message = (
            f"💰 Монеты: {balance}\n"
            f"💎 Кристаллы: {crystals}\n"
            f"🐾 Лимит животных: 0/{animal_limit}"
        )
        safe_send(vk, user_id, message)

    # --- РЕСУРСЫ ---
    elif lower_text in ["ресурсы", "инвентарь", "инв", "сундук"]:


        resources = get_resources(user_id)
        
        shop_items = {k: v for k, v in resources.items() if k.startswith("🛍️")}
        normal_resources = {k: v for k, v in resources.items() if not k.startswith("🛍️")}
        
        if not resources:
            safe_send(vk, user_id, "Твой сундук пока пуст.")
        else:
            message = "🎒 Твой сундук:\n\n"
            
            if shop_items:
                message += "🛍️ Предметы магазина:\n"
                for item_name, qty in shop_items.items():
                    display_name = item_name.replace("🛍️ ", "")
                    message += f"{display_name} : {qty} шт.\n"
                message += "\n"
            
            if normal_resources:
                lug_resources = ["💐🌸🌺 Цветы", "🍓 Ягоды", "🐁 Мыши", "🐦 Птицы",
                               "🦷 Клыки змеи", "🏻 Твёрдая шкура", "🍄 Грибы", "🔸 Золото"]
                lug_items = [f"{r} : {normal_resources[r]} шт." for r in lug_resources if r in normal_resources and normal_resources[r] > 0]
                if lug_items:
                    message += "🏞️ Ясный луг:\n" + "\n".join(lug_items) + "\n\n"
                
                forest_resources = ["🍯 Тёмный мёд", "🪨 Мшистый камень", "🌿 Папаротник-шептун",
                                  "🥜 Сонный орешек", "🌕 Лунный шёлк", "🍁 Золотой лист",
                                  "🦌 Рог оленя", "🕯️ Лесная свеча"]
                forest_items = [f"{r} : {normal_resources[r]} шт." for r in forest_resources if r in normal_resources and normal_resources[r] > 0]
                if forest_items:
                    message += "🌲 Тёмный лес:\n" + "\n".join(forest_items) + "\n\n"
                
                ice_resources = ["❄️ Искристый снег", "🍇 Морозные ягодки", "🐟 Серебряная рыбка",
                               "🐚 Ракушка", "🦉 Перо полярной совы", "⭐ Замёрзшая звезда"]
                ice_items = [f"{r} : {normal_resources[r]} шт." for r in ice_resources if r in normal_resources and normal_resources[r] > 0]
                if ice_items:
                    message += "❄️ Ледяное озеро:\n" + "\n".join(ice_items) + "\n\n"
                
                water_resources = ["💧 Эфирная капля", "🕊️ Облачное пёрышко", "🏵️ Туманный цветок",
                                 "🌊 Сладкая пена", "🌟 Искра водопада", "🦋 Водяная бабочка",
                                 "🌙 Лунный блик", "💥 Звёздная пыльца"]
                water_items = [f"{r} : {normal_resources[r]} шт." for r in water_resources if r in normal_resources and normal_resources[r] > 0]
                if water_items:
                    message += "💧 Эфирный водопад:\n" + "\n".join(water_items) + "\n\n"
                
                fairy_resources = ["🍎 Золотое яблоко", "🌰 Волшебный орех", "🕸️ Паутина",
                                 "📜 Свиток", "🔔 Колокольчик тишины", "☄️ Звездопадный камень"]
                fairy_items = [f"{r} : {normal_resources[r]} шт." for r in fairy_resources if r in normal_resources and normal_resources[r] > 0]
                if fairy_items:
                    message += "✨ Сказочный лес:\n" + "\n".join(fairy_items) + "\n\n"
            
            safe_send(vk, user_id, message)

    # --- ПРОМОКОДЫ ---
    elif lower_text.startswith("промокод") or lower_text.startswith("промо"):
        parts = text.split()
        if len(parts) == 2:
            code = parts[1]
            reward, error = check_promo(code, user_id)
            if reward:
                if "монеты" in reward:
                    add_balance(user_id, reward["монеты"])
                if "кристаллы" in reward:
                    add_crystals(user_id, reward["кристаллы"])
                if "ресурс" in reward:
                    for res_name, res_amount in reward["ресурс"].items():
                        add_resource(user_id, res_name, res_amount)
                safe_send(vk, user_id, "🎉 Промокод активирован! Проверь баланс.")
            else:
                safe_send(vk, user_id, error or "❌ Промокод недействителен.")
        else:
            safe_send(vk, user_id, "❌ Формат: Промокод НАЗВАНИЕ")

    # --- ПОПОЛНЕНИЕ ---
    elif lower_text.startswith("пополнить"):
        admins = get_admins()
        if user_id not in admins:
            safe_send(vk, user_id, "⛔ У тебя нет прав.")
            return
        parts = text.split()
        if len(parts) >= 3:
            target_type = parts[1].lower()
            if target_type == "монеты" and len(parts) == 4:
                try:
                    amount = int(parts[2])
                    target_id = int(parts[3])
                    add_balance(target_id, amount)
                    safe_send(vk, user_id, f"✅ {amount} монет → игроку {target_id}.")
                except:
                    safe_send(vk, user_id, "❌ Формат: Пополнить монеты СУММА ID")
            elif target_type == "кристаллы" and len(parts) == 4:
                try:
                    amount = int(parts[2])
                    target_id = int(parts[3])
                    add_crystals(target_id, amount)
                    safe_send(vk, user_id, f"✅ {amount} кристаллов → игроку {target_id}.")
                except:
                    safe_send(vk, user_id, "❌ Формат: Пополнить кристаллы СУММА ID")
            elif target_type == "лимит" and len(parts) == 4:
                try:
                    new_limit = int(parts[2])
                    target_id = int(parts[3])
                    set_animal_limit(target_id, new_limit)
                    safe_send(vk, user_id, f"✅ Лимит для {target_id} → {new_limit}.")
                except:
                    safe_send(vk, user_id, "❌ Формат: Пополнить лимит ЧИСЛО ID")
            elif target_type == "ресурс" and len(parts) >= 5:
                try:
                    target_id = int(parts[-1])
                    amount = int(parts[-2])
                    resource_name = " ".join(parts[2:-2])
                    if resource_name not in ALL_RESOURCES:
                        safe_send(vk, user_id, f"❌ Неизвестный ресурс: {resource_name}")
                        return
                    add_resource(target_id, resource_name, amount)
                    safe_send(vk, user_id, f"✅ {resource_name} x{amount} → игроку {target_id}.")
                except:
                    safe_send(vk, user_id, "❌ Формат: Пополнить ресурс НАЗВАНИЕ КОЛИЧЕСТВО ID")
            else:
                safe_send(vk, user_id, "❌ Напиши Админ для подсказки")
        else:
            safe_send(vk, user_id, "❌ Напиши Админ для подсказки")

    # --- ПОМОЩЬ ---
    elif lower_text in ["помощь", "команды"]:
        safe_send(vk, user_id, "🤔 Команды:\n• Баланс — твои монеты и кристаллы\n• Ресурсы — твой сундук\n• Магазин — купить предметы\n• Купить НАЗВАНИЕ — быстрая покупка")

    # --- АВТО-ПРОМОКОД ---
    else:
        code = text.strip()
        reward, error = check_promo(code, user_id)
        if reward:
            if "монеты" in reward:
                add_balance(user_id, reward["монеты"])
            if "кристаллы" in reward:
                add_crystals(user_id, reward["кристаллы"])
            if "ресурс" in reward:
                for res_name, res_amount in reward["ресурс"].items():
                    add_resource(user_id, res_name, res_amount)
            safe_send(vk, user_id, "🎉 Промокод активирован! Проверь баланс.")
        else:
            safe_send(vk, user_id, error or "🤔 Неизвестная команда. Напиши «Помощь».")

def main():
    vk_session = vk_api.VkApi(token=TOKEN)
    vk = vk_session.get_api()
    longpoll = VkBotLongPoll(vk_session, GROUP_ID)
    print("Бот запущен!")
    for event in longpoll.listen():
        if event.type == VkBotEventType.MESSAGE_NEW:
            handle_message(vk, event)

if __name__ == "__main__":
    main()
