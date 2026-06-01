import os 
import asyncio
import aiohttp
import re
import random
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ====================================
# НАСТРОЙКА ЛОГИРОВАНИЯ
# ====================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

# Функция для получения информации о пользователе
def get_user_info(user):
    """Возвращает подробную информацию о пользователе"""
    parts = [str(user.id)]
    if user.username:
        parts.append(f"@{user.username}")
    if user.first_name:
        parts.append(user.first_name)
    if user.last_name:
        parts.append(user.last_name)
    return " | ".join(parts)

# Универсальная функция для безопасного редактирования сообщений
async def safe_edit_message(message, text, reply_markup=None, parse_mode="Markdown"):
    """Редактирует сообщение, игнорируя ошибку 'message is not modified'"""
    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
        return True
    except Exception as e:
        if "message is not modified" in str(e):
            return False
        else:
            raise e

# ====================================
# TOKEN
# ====================================

TOKEN = os.getenv('Bot_token') 

bot = Bot(token=TOKEN)
dp = Dispatcher()
user_mode = {}
firebase_db_url = None

# Хранилище для теста (вопросы временно)
user_tests = {}


# ====================================
# БАЗЫ ДАННЫХ
# ====================================

# Рандом лодаут
WEAPONS = {
    "💰 Бюджет": [
        "SKS 7.62×39", "Mosin 7.62×54R", "PPSh-41", "MP5 9×19",
        "Vepr-136 7.62×39", "ADAR 5.56×45", "M870 12/70", "Saiga-9 9×19"
    ],
    "😎 Чад": [
        "HK416 5.56×45", "M4A1 5.56×45", "SR-25 7.62×51", "Vector 9×19",
        "AS VAL 9×39", "DVL-10 7.62×51", "P90 5.7×28", "MCX .300 Blackout"
    ],
    "🤡 Безумие": [
        "Топор", "Антивоблинговая граната", "ТТ 7.62×25", "Кирка",
        "MP-18 12/70", "PM 9×18", "RGD-5 (только гранаты)", "Нож",
        "Ничего (голые кулаки)", "Травмат"
    ]
}

ARMOR = {
    "💰 Бюджет": ["PACA", "6B23-1", "6B5-15", "Жилет от UN", "Module-3M"],
    "😎 Чад": ["Slick", "Hexgrid", "Korund", "TV-110", "AACPC"],
    "🤡 Безумие": ["Без брони", "Бронежилет 3M", "Спортивная куртка", "PACA (20%)", "Противогаз"]
}

MAPS = ["Customs", "Woods", "Shoreline", "Lighthouse", "Reserve", "Interchange", "Factory", "Streets of Tarkov"]

OBJECTIVES = [
    "Убить 5 Scav'ов", "Найти GPU", "Выжить и эвакуироваться",
    "Убить 3 PMC", "Найти LedX", "Убить рейд-босса",
    "True Survivor (без медицины)", "Собрать 100к лута",
    "Убить Goons", "Найти Красную карту", "Сделать 3 хедшота",
    "Не стрелять (только ближний бой)", "Найти и вынести бензин",
    "Взломать 3 замка", "Подобрать чужой жетон"
]

SPECIAL_RULES = [
    "🔇 Без наушников", "🚫 Без контейнера", "💀 Hardcore (без страховки)",
    "🎯 Только одиночный режим", "🤫 Zero to Hero (только нож)",
    "🍞 Без еды и воды", "💊 Без медикаментов", "🔦 Только ночь с фонариком",
    "👣 Только пешком", "🎒 Только маленький рюкзак", "🔫 Только найденное оружие"
]

# PMC Name Generator
PMC_PREFIXES = [
    "TUSHENKA", "KALASH", "HEAD_EYES", "SCAV", "KILLA", "TAGILLA",
    "RASHALA", "GLUKHAR", "DORMS", "CUSTOMS", "LABS", "FACTORY",
    "WOODS", "BITCOIN", "GP_COIN", "LEDX", "SALEWA", "MORPHINE",
    "VOG", "BP", "M995", "M80", "SNB", "MOSIN", "PRAPOR", "THERAPIST"
]

PMC_SUFFIXES = [
    "TERMINATOR", "SLAYER", "GOBLIN", "DEMON", "RAT", "CHAD",
    "HUNTER", "FARMER", "LOOTER", "CAMPER", "SNIPER", "BREACHER",
    "WARRIOR", "ENJOYER", "ADDICT", "MAIN", "GOD", "LEGEND",
    "NOOB", "TIMIK", "RUNNER", "EXTRACTOR", "BANDIT", "GHOST"
]

PMC_FUNNY_NAMES = [
    "Timmy_No_Thumbs", "Head_Eyes_Victim", "Bush_Wookie_Main",
    "Loot_Goblin_3000", "Scav_Aimbot", "One_Tap_Andy",
    "Extract_Camper", "Gear_Fear_Enjoyer", "Tarkov_Shitter",
    "Mosling_God", "Pixel_Peeker", "Desync_Abuser"
]

# Rat or Chad Test вопросы
RAT_CHAD_QUESTIONS = [
    {
        "question": "Ты слышишь шаги рядом. Твои действия:",
        "answers": [
            ("Затаиться в кустах и ждать 10 минут", -2),
            ("Агрессивно пушить с гранатой", 2),
            ("Оценить ситуацию, занять позицию", 1),
            ("Кричать в войс 'друг, не стреляй!'", -1)
        ]
    },
    {
        "question": "Твой идеальный рейд это:",
        "answers": [
            ("Тихо налутал 500к и ушёл незамеченным", -2),
            ("Зачистил половину сервера, вышел с фрагами", 2),
            ("Сделал квест и выжил", 0),
            ("Кампил выход 40 минут", -1)
        ]
    },
    {
        "question": "Что берёшь с собой в рейд?",
        "answers": [
            ("Пистолет и мечту", -2),
            ("Полный мета-сетап: HK416 + Slick", 2),
            ("Средний лодаут, но с хорошими патронами", 1),
            ("Голым, надеясь найти ствол на месте", -1)
        ]
    },
    {
        "question": "Видишь труп с лутом посреди улицы:",
        "answers": [
            ("Жду 5 минут, смотрю не кемперят ли", -2),
            ("Бегу лутать сразу, я быстрый", 2),
            ("Кидаю гранату для проверки, потом лут", 1),
            ("Обхожу стороной, это ловушка", -1)
        ]
    },
    {
        "question": "Твой любимый тип оружия:",
        "answers": [
            ("Снайперка с глушителем", -1),
            ("Автомат для CQB", 2),
            ("Дробовик, люблю ближний бой", 1),
            ("Всё равно, главное патроны получше", 0)
        ]
    }
]

# Tarkov News (актуальные на май 2026)
TARKOV_NEWS = [
    {
        "date": "25 мая 2026",
        "title": "🔥 Патч 1.0.5.0 и ивент «Ледокол»!",
        "text": "Вышло крупное обновление с PvE-локацией «Ледокол» — огромный атомный ледокол Paradigm Shipping, запертый в блокаде Таркова. Новая сюжетная глава «Борей», нелинейная история с выборами, кодовые панели, новый босс и кооператив до 3 человек. Карта только для PvE!"
    },
    {
        "date": "25 мая 2026",
        "title": "⚙️ Технические улучшения в патче 1.0.5.0",
        "text": "Помощник поиска квестовых предметов (направление к цели), новые наборы кастомизации USEC Gen 4 и BEAR Slavianka, экспериментальные настройки графики для RTX-карт, перенос нагрузки с CPU на GPU. Исправлены утечки памяти и ошибка 228."
    },
    {
        "date": "26-30 мая 2026",
        "title": "🎁 Twitch Drops кампания",
        "text": "Смотри стримы Escape from Tarkov на Twitch и получай внутриигровые наборы с оружием, снаряжением и редкими предметами. Кампания продлится до 30 мая. Также скидки на издания игры в официальном магазине."
    },
    {
        "date": "8-12 мая 2026",
        "title": "⚔️ Ивент на Таможне: Решала против Глухаря",
        "text": "Люди Решалы украли припасы РосРезерва, и Глухарь прибыл с карательным рейдом. Оба босса спавнятся со 100% шансом, Дикие убраны с карты, лимит игроков-Диких снижен до трёх. Конфликт банд на Таможне!"
    },
    {
        "date": "30 апреля 2026",
        "title": "💀 Ивент на Заводе: Килла и Тагилла",
        "text": "«Братья разрушения» появились на Заводе одновременно! Ивент только в дневных рейдах, Дикие отключены, переходы на карту заблокированы. По лору — зачистка для подпольных боёв. Крайне опасно!"
    },
    {
        "date": "Февраль 2026",
        "title": "🗺 Дорожная карта на первую половину 2026",
        "text": "Battlestate Games анонсировали: DLSS 4.5, переработка растительности на всех картах, новая анимация оружия, улучшение переподключения к рейдам, глобальный ивент «Ледокол» и озвучка ЧВК «Никита» с голосом самого Буянова."
    }
]


# ====================================
# GOONS (весь оригинальный код)
# ====================================

async def get_firebase_config(url):
    global firebase_db_url
    if firebase_db_url:
        return firebase_db_url
    
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=15) as response:
                html = await response.text()
                db_url_match = re.search(r'databaseURL["\s:]+(["\'])(https://[^\'"]+)\1', html)
                if db_url_match:
                    firebase_db_url = db_url_match.group(2)
                    return firebase_db_url
    except Exception as e:
        print(f"Ошибка конфига: {e}")
    return None


def parse_time(time_str):
    if not time_str:
        return None
    time_str = str(time_str).strip()
    try:
        if 'T' in time_str and ('Z' in time_str or '+' in time_str):
            return datetime.fromisoformat(time_str.replace('Z', '+00:00')).replace(tzinfo=None)
    except:
        pass
    formats = ['%m/%d/%Y, %I:%M:%S %p', '%m/%d/%Y, %H:%M:%S']
    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt)
        except:
            continue
    return None


def format_time_ago(dt):
    if not dt:
        return ""
    now = datetime.now()
    delta = now - dt
    total_minutes = int(delta.total_seconds() / 60)
    if total_minutes < 1:
        return "только что"
    elif total_minutes < 60:
        return f"{total_minutes} мин назад"
    elif total_minutes < 1440:
        hours = total_minutes // 60
        mins = total_minutes % 60
        if mins > 0:
            return f"{hours} ч {mins} мин назад"
        return f"{hours} ч назад"
    elif total_minutes < 10080:
        days = total_minutes // 1440
        hours = (total_minutes % 1440) // 60
        return f"{days} дн {hours} ч назад"
    else:
        return dt.strftime('%d.%m.%Y в %H:%M')


async def get_goons_data():
    global firebase_db_url
    if not firebase_db_url:
        return None, None
    try:
        reports_url = f"{firebase_db_url}/reports.json"
        async with aiohttp.ClientSession() as session:
            async with session.get(reports_url, timeout=10) as response:
                if response.status != 200:
                    return None, None
                data = await response.json()
                if not data:
                    return None, None
                now = datetime.now()
                pvp_reports = []
                pve_reports = []
                for key, report in data.items():
                    if not isinstance(report, dict):
                        continue
                    mode = report.get('mode')
                    if mode is None or str(mode).strip().upper() == 'NO_MODE':
                        continue
                    mode = str(mode).strip().upper()
                    parsed_time = parse_time(report.get('time', ''))
                    if not parsed_time or parsed_time > now:
                        continue
                    report['_time'] = parsed_time
                    if mode == 'PVP':
                        pvp_reports.append(report)
                    elif mode == 'PVE':
                        pve_reports.append(report)
                pvp_reports.sort(key=lambda x: x['_time'], reverse=True)
                pve_reports.sort(key=lambda x: x['_time'], reverse=True)
                return pvp_reports, pve_reports
    except Exception as e:
        print(f"Firebase ошибка: {e}")
        return None, None


def format_report(reports):
    if not reports:
        return "❌ Нет репортов"
    latest = reports[0]
    map_name = latest.get('map', 'Неизвестно')
    tracker = latest.get('tracker', 'Аноним')
    ago = format_time_ago(latest['_time'])
    delta = datetime.now() - latest['_time']
    if delta < timedelta(hours=2):
        icon = "🟢"
    elif delta < timedelta(hours=24):
        icon = "🟡"
    else:
        icon = "🔴"
    return f"{icon} {map_name} — {ago}\n   👤 {tracker}"


async def get_goons():
    global firebase_db_url
    if not firebase_db_url:
        await get_firebase_config("https://goontrackertarkov.com/pvp-goon-tracker")
    if not firebase_db_url:
        return "❌ Нет связи", "❌ Нет связи"
    pvp_data, pve_data = await get_goons_data()
    pvp_result = format_report(pvp_data) if pvp_data is not None else "❌ Ошибка"
    pve_result = format_report(pve_data) if pve_data is not None else "❌ Ошибка"
    return pvp_result, pve_result


# ====================================
# РАНДОМ ЛОДАУТ
# ====================================

def generate_loadout():
    tiers = list(WEAPONS.keys())
    weights = [40, 35, 25]
    tier = random.choices(tiers, weights=weights, k=1)[0]
    weapon = random.choice(WEAPONS[tier])
    armor = random.choice(ARMOR[tier])
    map_name = random.choice(MAPS)
    objectives = random.sample(OBJECTIVES, min(2, len(OBJECTIVES)))
    is_night = random.choice([True, False])
    if is_night:
        hour = random.randint(21, 23) if random.random() < 0.5 else random.randint(0, 5)
        time_str = f"{hour:02d}:00 🌙 (ночь)"
    else:
        time_str = f"{random.randint(6, 17):02d}:00 ☀️ (день)"
    rules_count = {
        "💰 Бюджет": random.randint(0, 1),
        "😎 Чад": random.randint(0, 2),
        "🤡 Безумие": random.randint(2, 3)
    }
    special_rules = random.sample(SPECIAL_RULES, min(rules_count[tier], len(SPECIAL_RULES)))
    return {
        "tier": tier, "weapon": weapon, "armor": armor,
        "map": map_name, "time": time_str,
        "objectives": objectives, "special_rules": special_rules
    }


def format_loadout_text(loadout):
    objectives_text = "\n".join([f"  • {obj}" for obj in loadout["objectives"]])
    if loadout["special_rules"]:
        rules_text = "\n".join([f"  {rule}" for rule in loadout["special_rules"]])
    else:
        rules_text = "  ✅ Без ограничений"
    endings = {
        "💰 Бюджет": "Ну, с богом. Экономь патроны, бирец.",
        "😎 Чад": "Ты машина для убийств. Иди и властвуй, бирец.",
        "🤡 Безумие": "Ты псих, бирец. Серьёзно. Но это легендарно."
    }
    return (
        f"🎲 **РАНДОМ ЛОДАУТ**\n"
        f"🏷 **{loadout['tier']}**\n\n"
        f"🔫 **Оружие:** {loadout['weapon']}\n"
        f"🛡 **Броня:** {loadout['armor']}\n"
        f"🗺 **Карта:** {loadout['map']}\n"
        f"🕐 **Время:** {loadout['time']}\n\n"
        f"🎯 **Цели:**\n{objectives_text}\n\n"
        f"⚠️ **Особые правила:**\n{rules_text}\n\n"
        f"_{endings[loadout['tier']]}_"
    )


# ====================================
# PMC NAME GENERATOR
# ====================================

def generate_pmc_name():
    """Генерирует случайный PMC ник"""
    choice = random.random()
    if choice < 0.4:
        prefix = random.choice(PMC_PREFIXES)
        suffix = random.choice(PMC_SUFFIXES)
        return f"{prefix}_{suffix}"
    elif choice < 0.7:
        return random.choice(PMC_FUNNY_NAMES)
    else:
        prefix = random.choice(PMC_PREFIXES)
        suffix = random.choice(PMC_SUFFIXES)
        number = random.randint(1, 9999)
        return f"{prefix}_{suffix}_{number}"


# ====================================
# RAT OR CHAD TEST
# ====================================

def calculate_rat_chad(answers):
    """Подсчёт результата теста"""
    total = sum(answers)
    if total <= -5:
        return "🐀 **100% КРЫСА**\n\nТы мастер кустов и теней. Твой девиз: 'Лучше сидеть 40 минут в туалете, чем потерять Slick'. Ты выходишь с рейда с полным рюкзаком и нулём фрагов."
    elif total <= -2:
        return "🐀 **Крыса с амбициями** (70% Крыса / 30% Чад)\n\nТы предпочитаешь тихий лут, но иногда можешь и огрызнуться. В основном сидишь в кустах, но если припрут — покажешь зубки."
    elif total <= 2:
        return "⚖️ **Базовый игрок** (50% Крыса / 50% Чад)\n\nТы адаптируешься под ситуацию. Можешь и закемперить угол, и агрессивно запушить. Универсальный солдат."
    elif total <= 5:
        return "😎 **Чад с инстинктами** (70% Чад / 30% Крыса)\n\nТы любишь экшн, но не бездумно. Сначала думаешь, потом пушишь. Опасный противник."
    else:
        return "😎 **100% ЧАД**\n\nТы рождён для PvP. Твой девиз: 'Лучший лут — это трупы врагов'. Ты пушишь всё что движется и не движется."


# ====================================
# КЛАВИАТУРЫ
# ====================================

def get_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="☠ Гуны", callback_data="goons_menu"))
    builder.row(InlineKeyboardButton(text="🎲 Рандом лодаут", callback_data="random_loadout"))
    builder.row(
        InlineKeyboardButton(text="🐀 Крыса или Чад?", callback_data="rat_chad_test"),
        InlineKeyboardButton(text="🎖 Генератор ника", callback_data="pmc_name")
    )
    builder.row(InlineKeyboardButton(text="📰 Новости Tarkov", callback_data="tarkov_news"))
    return builder.as_markup()

def get_goons_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎮 PvP", callback_data="goons_pvp"),
        InlineKeyboardButton(text="🛡️ PvE", callback_data="goons_pve")
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Оба", callback_data="goons_all"),
        InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")
    )
    return builder.as_markup()

def get_loadout_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎲 Крутить ещё!", callback_data="random_loadout"))
    builder.row(InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu"))
    return builder.as_markup()

def get_refresh_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_goons"))
    builder.row(InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu"))
    return builder.as_markup()

def get_back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu"))
    return builder.as_markup()


# ====================================
# START
# ====================================

@dp.message(Command("start"))
async def start(message: types.Message):
    user = message.from_user
    user_info = get_user_info(user)
    logger.info(f"🚀 START | {user_info}")
    await message.answer(
        "🎯 **TARKOV ASSISTANT v4.0**\n\n"
        "☠ Отслеживание гунов\n"
        "🎲 Рандомные лодауты\n"
        "🐀 Тест Крыса/Чад\n"
        "🎖 Генератор ника\n"
        "📰 Новости Tarkov\n\n"
        "Выбирай, бирец:",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )


# ====================================
# ГЛАВНОЕ МЕНЮ
# ====================================

@dp.callback_query(lambda c: c.data == "main_menu")
async def main_menu_callback(callback: types.CallbackQuery):
    user = callback.from_user
    user_info = get_user_info(user)
    logger.info(f"🏠 MAIN_MENU | {user_info}")
    await callback.answer("Главное меню")
    
    await safe_edit_message(
        callback.message,
        "🎯 **TARKOV ASSISTANT v4.0**\n\n"
        "Выбирай, бирец:",
        get_main_keyboard()
    )


# ====================================
# GOONS
# ====================================

@dp.callback_query(lambda c: c.data == "goons_menu")
async def goons_menu_callback(callback: types.CallbackQuery):
    user = callback.from_user
    user_info = get_user_info(user)
    logger.info(f"☠ GOONS_MENU | {user_info}")
    await callback.answer("Гуны")
    
    await safe_edit_message(
        callback.message,
        "☠ **GOONS TRACKER**\n\nВыберите режим:",
        get_goons_keyboard()
    )

@dp.callback_query(lambda c: c.data.startswith("goons_"))
async def goons_quick_callback(callback: types.CallbackQuery):
    mode = callback.data.split("_")[1]
    user = callback.from_user
    user_info = get_user_info(user)
    logger.info(f"☠ GOONS_CHECK | {user_info} | Mode: {mode}")
    
    if mode in ["pvp", "pve", "all"]:
        user_mode[user.id] = mode
    await callback.answer("Загружаю...")
    pvp_loc, pve_loc = await get_goons()
    time_str = datetime.now().strftime('%H:%M:%S')
    
    if mode == "pvp":
        text = f"☠ **GOONS — PvP**\n\n{pvp_loc}\n\n🕒 {time_str}"
    elif mode == "pve":
        text = f"☠ **GOONS — PvE**\n\n{pve_loc}\n\n🕒 {time_str}"
    else:
        text = f"☠ **GOONS TRACKER**\n\n🎮 PvP:\n{pvp_loc}\n\n🛡️ PvE:\n{pve_loc}\n\n🕒 {time_str}"
    
    await safe_edit_message(callback.message, text, get_refresh_keyboard())

@dp.message(Command("goons"))
async def goons(message: types.Message):
    user = message.from_user
    user_info = get_user_info(user)
    user_id = user.id
    mode_filter = user_mode.get(user_id, "all")
    logger.info(f"☠ GOONS_CMD | {user_info} | Mode: {mode_filter}")
    
    msg = await message.answer("🔍 Загружаю данные...")
    pvp_loc, pve_loc = await get_goons()
    time_str = datetime.now().strftime('%H:%M:%S')
    if mode_filter == "pvp":
        text = f"☠ **GOONS — PvP**\n\n{pvp_loc}\n\n🕒 {time_str}"
    elif mode_filter == "pve":
        text = f"☠ **GOONS — PvE**\n\n{pve_loc}\n\n🕒 {time_str}"
    else:
        text = f"☠ **GOONS TRACKER**\n\n🎮 PvP:\n{pvp_loc}\n\n🛡️ PvE:\n{pve_loc}\n\n🕒 {time_str}"
    await msg.edit_text(text, reply_markup=get_refresh_keyboard(), parse_mode="Markdown")

@dp.callback_query(lambda c: c.data == "refresh_goons")
async def refresh_callback(callback: types.CallbackQuery):
    user = callback.from_user
    user_info = get_user_info(user)
    user_id = user.id
    mode_filter = user_mode.get(user_id, "all")
    logger.info(f"🔄 REFRESH_GOONS | {user_info} | Mode: {mode_filter}")
    
    await callback.answer("Обновляю...")
    pvp_loc, pve_loc = await get_goons()
    time_str = datetime.now().strftime('%H:%M:%S')
    if mode_filter == "pvp":
        text = f"☠ **GOONS — PvP**\n\n{pvp_loc}\n\n🕒 {time_str}"
    elif mode_filter == "pve":
        text = f"☠ **GOONS — PvE**\n\n{pve_loc}\n\n🕒 {time_str}"
    else:
        text = f"☠ **GOONS**\n\n🎮 PvP:\n{pvp_loc}\n\n🛡️ PvE:\n{pve_loc}\n\n🕒 {time_str}"
    
    await safe_edit_message(callback.message, text, get_refresh_keyboard())


# ====================================
# РАНДОМ ЛОДАУТ
# ====================================

@dp.message(Command("roll"))
async def roll_command(message: types.Message):
    user = message.from_user
    user_info = get_user_info(user)
    loadout = generate_loadout()
    logger.info(f"🎲 LOADOUT_CMD | {user_info} | Tier: {loadout['tier']} | Map: {loadout['map']}")
    
    text = format_loadout_text(loadout)
    await message.answer(text, reply_markup=get_loadout_keyboard(), parse_mode="Markdown")

@dp.callback_query(lambda c: c.data == "random_loadout")
async def random_loadout_callback(callback: types.CallbackQuery):
    user = callback.from_user
    user_info = get_user_info(user)
    
    await callback.answer("Крутим лодаут...")
    loadout = generate_loadout()
    logger.info(f"🎲 LOADOUT | {user_info} | Tier: {loadout['tier']} | Map: {loadout['map']}")
    
    text = format_loadout_text(loadout)
    await safe_edit_message(callback.message, text, get_loadout_keyboard())


# ====================================
# PMC NAME GENERATOR
# ====================================

@dp.message(Command("nick"))
async def nick_command(message: types.Message):
    user = message.from_user
    user_info = get_user_info(user)
    name = generate_pmc_name()
    logger.info(f"🎖 NICK_CMD | {user_info} | Generated: {name}")
    
    await message.answer(
        f"🎖 **Твой PMC ник:**\n\n"
        f"`{name}`\n\n"
        f"_Отлично подходит для Tarkov! Неси смерть с этим именем, бирец._",
        reply_markup=get_loadout_keyboard(),
        parse_mode="Markdown"
    )

@dp.callback_query(lambda c: c.data == "pmc_name")
async def pmc_name_callback(callback: types.CallbackQuery):
    user = callback.from_user
    user_info = get_user_info(user)
    name = generate_pmc_name()
    logger.info(f"🎖 NICK_GEN | {user_info} | Generated: {name}")
    
    await callback.answer("Генерирую ник...")
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎖 Ещё ник", callback_data="pmc_name"))
    builder.row(InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu"))
    
    await safe_edit_message(
        callback.message,
        f"🎖 **ГЕНЕРАТОР PMC НИКА**\n\n"
        f"Твой новый ник:\n"
        f"`{name}`\n\n"
        f"_Готов к рейду, бирец?_",
        builder.as_markup()
    )


# ====================================
# RAT OR CHAD TEST
# ====================================

@dp.message(Command("test"))
async def test_command(message: types.Message):
    user = message.from_user
    user_info = get_user_info(user)
    logger.info(f"🐀 TEST_START_CMD | {user_info}")
    await start_rat_chad_test(message)

@dp.callback_query(lambda c: c.data == "rat_chad_test")
async def rat_chad_test_callback(callback: types.CallbackQuery):
    user = callback.from_user
    user_info = get_user_info(user)
    logger.info(f"🐀 TEST_START | {user_info}")
    await start_rat_chad_test(callback.message)
    await callback.answer("Начинаем тест!")

async def start_rat_chad_test(message):
    """Запуск теста Крыса/Чад"""
    user_id = message.from_user.id if isinstance(message, types.Message) else message.chat.id
    
    user_tests[user_id] = {
        "answers": [],
        "current_question": 0
    }
    
    await send_question(message, user_id)

async def send_question(message, user_id):
    """Отправка следующего вопроса"""
    test_data = user_tests.get(user_id, {})
    question_num = test_data.get("current_question", 0)
    
    if question_num >= len(RAT_CHAD_QUESTIONS):
        result = calculate_rat_chad(test_data.get("answers", []))
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔄 Пройти заново", callback_data="rat_chad_test"))
        builder.row(InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu"))
        
        text = f"🐀 **RAT OR CHAD TEST** 😎\n\n{result}"
        
        if isinstance(message, types.Message):
            await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        else:
            await safe_edit_message(message, text, builder.as_markup())
        
        if user_id in user_tests:
            del user_tests[user_id]
        return
    
    question = RAT_CHAD_QUESTIONS[question_num]
    
    builder = InlineKeyboardBuilder()
    for i, (answer_text, _) in enumerate(question["answers"]):
        builder.row(InlineKeyboardButton(
            text=answer_text, 
            callback_data=f"rat_chad_answer_{question_num}_{i}"
        ))
    
    text = f"🐀 **RAT OR CHAD TEST** 😎\n\n"
    text += f"Вопрос {question_num + 1}/{len(RAT_CHAD_QUESTIONS)}:\n\n"
    text += f"**{question['question']}**"
    
    if isinstance(message, types.Message):
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    else:
        await safe_edit_message(message, text, builder.as_markup())

@dp.callback_query(lambda c: c.data.startswith("rat_chad_answer_"))
async def rat_chad_answer_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user = callback.from_user
    user_info = get_user_info(user)
    
    if user_id not in user_tests:
        logger.warning(f"⚠️ TEST_NOT_FOUND | {user_info}")
        await callback.answer("Тест не найден. Начни заново: /test")
        return
    
    parts = callback.data.split("_")
    question_num = int(parts[3])
    answer_num = int(parts[4])
    
    score = RAT_CHAD_QUESTIONS[question_num]["answers"][answer_num][1]
    user_tests[user_id]["answers"].append(score)
    user_tests[user_id]["current_question"] = question_num + 1
    
    logger.info(f"📝 TEST_ANSWER | {user_info} | Q{question_num + 1}/{len(RAT_CHAD_QUESTIONS)} | Score: {score}")
    await callback.answer(f"Ответ принят! ({question_num + 1}/{len(RAT_CHAD_QUESTIONS)})")
    
    await send_question(callback.message, user_id)


# ====================================
# TARKOV NEWS
# ====================================

@dp.message(Command("news"))
async def news_command(message: types.Message):
    user = message.from_user
    user_info = get_user_info(user)
    logger.info(f"📰 NEWS_CMD | {user_info}")
    await send_news(message)

@dp.callback_query(lambda c: c.data == "tarkov_news")
async def tarkov_news_callback(callback: types.CallbackQuery):
    user = callback.from_user
    user_info = get_user_info(user)
    logger.info(f"📰 NEWS | {user_info}")
    await send_news(callback.message)
    await callback.answer("Загружаю новости...")

async def send_news(message):
    """Отправка новостей Tarkov"""
    selected_news = random.sample(TARKOV_NEWS, min(3, len(TARKOV_NEWS)))
    
    text = "📰 **НОВОСТИ TARKOV**\n\n"
    
    for news in selected_news:
        text += f"📅 **{news['date']}**\n"
        text += f"**{news['title']}**\n"
        text += f"{news['text']}\n\n"
    
    text += "_Новости собраны из официальных источников. Следи за обновлениями, бирец._"
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔄 Обновить новости", callback_data="tarkov_news"))
    builder.row(InlineKeyboardButton(text="🔙 В меню", callback_data="main_menu"))
    
    if isinstance(message, types.Message):
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    else:
        await safe_edit_message(message, text, builder.as_markup())


# ====================================
# MAIN
# ====================================

async def main():
    logger.info("="*50)
    logger.info("🎯 TARKOV ASSISTANT v4.0 ЗАПУЩЕН")
    logger.info("☠ Goons + 🎲 Loadouts + 🐀 Rat/Chad + 🎖 Nick + 📰 News")
    logger.info("="*50)
    
    print("\n📡 Бот запущен... Логи смотрятся в веб-интерфейсе Railway\n")
    
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
