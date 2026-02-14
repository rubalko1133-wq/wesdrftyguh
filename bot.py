#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import subprocess
import sys
import importlib
import os
import time

# ================== АВТОМАТИЧЕСКАЯ УСТАНОВКА ЗАВИСИМОСТЕЙ ==================
def install_package(package):
    """Устанавливает пакет через pip"""
    print(f"📦 Устанавливаю {package}...")
    try:
        subprocess.check_call([
            sys.executable, 
            "-m", 
            "pip", 
            "install", 
            "--upgrade", 
            "--no-cache-dir", 
            package
        ])
        print(f"✅ {package} установлен")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Ошибка установки {package}: {e}")
        return False

# Сначала проверяем и устанавливаем базовые пакеты
required_packages = ["pandas", "openpyxl", "aiogram"]

print("🔍 Проверка зависимостей...")

for package in required_packages:
    try:
        importlib.import_module(package)
        print(f"✅ {package} уже установлен")
    except ImportError:
        print(f"❌ {package} не найден")
        if install_package(package):
            print(f"✅ {package} успешно установлен")
        else:
            print(f"❌ Не удалось установить {package}")
            print("Попробуйте установить вручную:")
            print(f"pip install {package}")
            sys.exit(1)

# Даем время на завершение установки
time.sleep(1)

# Теперь импортируем все модули
print("\n🔄 Загрузка модулей...")

try:
    import pandas as pd
    print("✅ pandas импортирован")
except ImportError as e:
    print(f"❌ Ошибка импорта pandas: {e}")
    sys.exit(1)

try:
    import openpyxl
    print("✅ openpyxl импортирован")
except ImportError as e:
    print(f"❌ Ошибка импорта openpyxl: {e}")
    sys.exit(1)

try:
    from aiogram import Bot, Dispatcher, F, types
    from aiogram.filters import Command
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, BufferedInputFile
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.enums import ParseMode
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.state import State, StatesGroup
    from aiogram.fsm.storage.memory import MemoryStorage
    print("✅ aiogram импортирован")
except ImportError as e:
    print(f"❌ Ошибка импорта aiogram: {e}")
    sys.exit(1)

# Импортируем остальные стандартные библиотеки
import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Union, Dict, Optional
from enum import Enum
from io import BytesIO

print("✅ Все модули успешно загружены!\n")

# Импортируем настройки из отдельного файла
try:
    from config import (
        BOT_TOKEN,
        CHANNEL_ID,
        ADMIN_IDS,
        BOT_NAME,
        DB_PATH,
        DEBUG_MODE,
        WELCOME_MESSAGE,
        ADMIN_WELCOME
    )
    print("✅ Конфигурация загружена")
except ImportError as e:
    print("=" * 50)
    print("❌ ОШИБКА: Файл config.py не найден!")
    print("Создайте файл config.py в той же папке")
    print("=" * 50)
    sys.exit(1)

# ================== ПРОВЕРКА НАСТРОЕК ==================
if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
    print("=" * 50)
    print("❌ ОШИБКА: Вы не указали токен бота в файле config.py!")
    print("Откройте config.py и вставьте свой токен от @BotFather")
    print("=" * 50)
    sys.exit(1)

if CHANNEL_ID == -1001234567890:
    print("=" * 50)
    print("⚠️ ВНИМАНИЕ: Вы не изменили ID канала в config.py!")
    print("Бот будет работать, но посты будут уходить в тестовый канал")
    print("=" * 50)

# ================== НАСТРОЙКА ЛОГИРОВАНИЯ ==================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if DEBUG_MODE:
    logger.setLevel(logging.DEBUG)
    logger.debug("🔧 Режим отладки включен")

# ================== ИНИЦИАЛИЗАЦИЯ БОТА ==================
storage = MemoryStorage()
try:
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=storage)
    logger.info(f"✅ Бот {BOT_NAME} инициализирован")
except Exception as e:
    logger.error(f"❌ Ошибка инициализации бота: {e}")
    sys.exit(1)

# ================== СОСТОЯНИЯ ==================
class AdminStates(StatesGroup):
    waiting_for_ban_reason = State()
    waiting_for_export_date = State()

class PostStatus(Enum):
    NEW = "new"
    TAKEN = "taken"
    PUBLISHED = "published"
    REJECTED = "rejected"

# ================== РАБОТА С БАЗОЙ ДАННЫХ ==================
def init_db():
    """Создание таблиц в базе данных"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Таблица для хранения ВСЕХ данных отправителей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                message_text TEXT,
                message_type TEXT,
                file_id TEXT,
                caption TEXT,
                received_date TEXT,
                forward_message_id INTEGER UNIQUE,
                status TEXT DEFAULT 'new',
                taken_by INTEGER DEFAULT NULL,
                taken_date TEXT DEFAULT NULL,
                published_date TEXT DEFAULT NULL,
                channel_message_id INTEGER DEFAULT 0
            )
        ''')
        
        # Таблица забаненных пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY,
                ban_date TEXT,
                reason TEXT,
                banned_by INTEGER
            )
        ''')
        
        # Таблица для логов действий админов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id INTEGER,
                action TEXT,
                target_user_id INTEGER,
                details TEXT,
                action_date TEXT
            )
        ''')
        
        # Таблица настроек админов
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_settings (
                admin_id INTEGER PRIMARY KEY,
                receive_all_posts INTEGER DEFAULT 1,
                notify_on_taken INTEGER DEFAULT 1
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"✅ База данных {DB_PATH} инициализирована")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при инициализации БД: {e}")
        return False

def save_user_message(user_id: int, username: str, first_name: str, last_name: str, 
                      message_text: str, message_type: str, file_id: str, caption: str, 
                      forward_msg_id: int):
    """Сохранение данных отправителя в базу"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO user_messages 
            (user_id, username, first_name, last_name, message_text, message_type, 
             file_id, caption, received_date, forward_message_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, username, first_name, last_name, message_text, message_type,
            file_id, caption, datetime.now().isoformat(), forward_msg_id, PostStatus.NEW.value
        ))
        conn.commit()
        conn.close()
        logger.debug(f"✅ Сообщение от {user_id} сохранено в БД")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения сообщения: {e}")
        return False

def update_message_status(forward_msg_id: int, status: PostStatus, taken_by: int = None, channel_msg_id: int = None):
    """Обновление статуса сообщения"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        if status == PostStatus.TAKEN and taken_by:
            cursor.execute('''
                UPDATE user_messages 
                SET status = ?, taken_by = ?, taken_date = ? 
                WHERE forward_message_id = ?
            ''', (status.value, taken_by, datetime.now().isoformat(), forward_msg_id))
        
        elif status == PostStatus.PUBLISHED and channel_msg_id:
            cursor.execute('''
                UPDATE user_messages 
                SET status = ?, published_date = ?, channel_message_id = ? 
                WHERE forward_message_id = ?
            ''', (status.value, datetime.now().isoformat(), channel_msg_id, forward_msg_id))
        
        elif status == PostStatus.REJECTED:
            cursor.execute('''
                UPDATE user_messages 
                SET status = ? 
                WHERE forward_message_id = ?
            ''', (status.value, forward_msg_id))
        
        conn.commit()
        conn.close()
        logger.debug(f"✅ Статус сообщения {forward_msg_id} обновлен на {status.value}")
        return True
    except Exception as e:
        logger.error(f"Ошибка обновления статуса: {e}")
        return False

def get_message_info(forward_msg_id: int) -> dict:
    """Получение информации о сообщении"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT user_id, username, first_name, last_name, message_text, 
                   message_type, received_date, status, taken_by, channel_message_id
            FROM user_messages WHERE forward_message_id = ?
        ''', (forward_msg_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'user_id': result[0],
                'username': result[1],
                'first_name': result[2],
                'last_name': result[3],
                'message_text': result[4],
                'message_type': result[5],
                'received_date': result[6],
                'status': result[7],
                'taken_by': result[8],
                'channel_msg_id': result[9]
            }
    except Exception as e:
        logger.error(f"Ошибка получения информации: {e}")
    return None

def export_to_excel(admin_id: int, days: int = None) -> BytesIO:
    """Экспорт данных в Excel"""
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # Формируем запрос
        query = '''
            SELECT 
                user_id as "ID пользователя",
                username as "Username",
                first_name as "Имя",
                last_name as "Фамилия",
                message_text as "Текст сообщения",
                message_type as "Тип",
                received_date as "Дата получения",
                status as "Статус",
                taken_by as "Взял админ",
                taken_date as "Дата взятия",
                published_date as "Дата публикации",
                channel_message_id as "ID в канале"
            FROM user_messages
        '''
        
        if days:
            cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
            query += f" WHERE received_date >= '{cutoff_date}'"
        
        query += " ORDER BY received_date DESC"
        
        # Читаем в pandas
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        # Создаем Excel файл в памяти
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Сообщения', index=False)
            
            # Настраиваем ширину колонок
            worksheet = writer.sheets['Сообщения']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        output.seek(0)
        logger.info(f"✅ Экспорт данных выполнен админом {admin_id}")
        return output
    except Exception as e:
        logger.error(f"❌ Ошибка экспорта в Excel: {e}")
        return None

def get_user_stats(user_id: int = None) -> dict:
    """Получение статистики"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        if user_id:
            cursor.execute('''
                SELECT COUNT(*), 
                       SUM(CASE WHEN status = 'published' THEN 1 ELSE 0 END),
                       MAX(received_date)
                FROM user_messages WHERE user_id = ?
            ''', (user_id,))
            total, published, last = cursor.fetchone()
            result = {
                'total': total or 0,
                'published': published or 0,
                'last_message': last
            }
        else:
            cursor.execute('SELECT COUNT(*) FROM user_messages')
            total = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM user_messages WHERE status = 'published'")
            published = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM user_messages WHERE status = 'new'")
            new = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM user_messages WHERE status = 'taken'")
            taken = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM banned_users")
            banned = cursor.fetchone()[0]
            
            result = {
                'total': total,
                'published': published,
                'new': new,
                'taken': taken,
                'banned': banned
            }
        
        conn.close()
        return result
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        return {}

def is_user_banned(user_id: int) -> bool:
    """Проверка бана"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT reason FROM banned_users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except:
        return False

def ban_user(user_id: int, admin_id: int, reason: str):
    """Бан пользователя"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO banned_users (user_id, ban_date, reason, banned_by) 
            VALUES (?, ?, ?, ?)
        ''', (user_id, datetime.now().isoformat(), reason, admin_id))
        conn.commit()
        conn.close()
        logger.info(f"✅ Пользователь {user_id} забанен админом {admin_id}")
    except Exception as e:
        logger.error(f"Ошибка бана: {e}")

def unban_user(user_id: int):
    """Разбан пользователя"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM banned_users WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
        logger.info(f"✅ Пользователь {user_id} разбанен")
    except Exception as e:
        logger.error(f"Ошибка разбана: {e}")

def log_admin_action(admin_id: int, action: str, target_user_id: int = None, details: str = ""):
    """Логирование действий админа"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO admin_logs (admin_id, action, target_user_id, details, action_date) 
            VALUES (?, ?, ?, ?, ?)
        ''', (admin_id, action, target_user_id, details, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Ошибка логирования: {e}")

# ================== КЛАВИАТУРЫ ==================
def get_moderation_keyboard(forward_id: int, taken_by: int = None) -> InlineKeyboardMarkup:
    """Клавиатура для модерации"""
    builder = InlineKeyboardBuilder()
    
    if taken_by:
        builder.row(InlineKeyboardButton(
            text=f"👤 В работе у {taken_by}",
            callback_data="noop"
        ))
    
    builder.row(
        InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"pub_{forward_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rej_{forward_id}")
    )
    
    if not taken_by:
        builder.row(
            InlineKeyboardButton(text="📌 Взять в работу", callback_data=f"take_{forward_id}")
        )
    
    builder.row(
        InlineKeyboardButton(text="🚫 Забанить автора", callback_data=f"ban_{forward_id}")
    )
    
    return builder.as_markup()

# ================== КОМАНДЫ АДМИНОВ ==================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Старт для всех пользователей"""
    user_id = message.from_user.id
    
    if is_user_banned(user_id):
        await message.answer("⛔ Вы заблокированы.")
        return
    
    # Если это админ - показываем админ-меню
    if user_id in ADMIN_IDS:
        await message.answer(ADMIN_WELCOME, parse_mode=ParseMode.MARKDOWN)
        return
    
    await message.answer(WELCOME_MESSAGE)

@dp.message(Command("export"))
async def cmd_export(message: types.Message):
    """Экспорт всех сообщений в Excel"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    await message.answer("📊 Генерирую Excel-файл со всеми сообщениями...")
    
    excel_file = export_to_excel(message.from_user.id)
    
    if excel_file:
        await message.answer_document(
            BufferedInputFile(
                excel_file.getvalue(),
                filename=f"messages_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            ),
            caption="✅ Все сообщения"
        )
        log_admin_action(message.from_user.id, 'export_all')
    else:
        await message.answer("❌ Ошибка при создании файла")

@dp.message(Command("export_days"))
async def cmd_export_days(message: types.Message):
    """Экспорт сообщений за N дней"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Использование: /export_days [количество дней]")
        return
    
    try:
        days = int(args[1])
        await message.answer(f"📊 Генерирую Excel-файл за последние {days} дней...")
        
        excel_file = export_to_excel(message.from_user.id, days)
        
        if excel_file:
            await message.answer_document(
                BufferedInputFile(
                    excel_file.getvalue(),
                    filename=f"messages_last_{days}_days_{datetime.now().strftime('%Y%m%d')}.xlsx"
                ),
                caption=f"✅ Сообщения за {days} дней"
            )
            log_admin_action(message.from_user.id, 'export_days', details=f"{days} days")
        else:
            await message.answer("❌ Ошибка при создании файла")
    except ValueError:
        await message.answer("❌ Некорректное число дней")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Общая статистика"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    stats = get_user_stats()
    
    text = f"""
📊 **ОБЩАЯ СТАТИСТИКА**

📝 Всего сообщений: {stats.get('total', 0)}
✅ Опубликовано: {stats.get('published', 0)}
🆕 Новых: {stats.get('new', 0)}
📌 В работе: {stats.get('taken', 0)}
🚫 Забанено: {stats.get('banned', 0)}
    """
    await message.answer(text, parse_mode=ParseMode.MARKDOWN)

@dp.message(Command("user_stats"))
async def cmd_user_stats(message: types.Message):
    """Статистика пользователя"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Использование: /user_stats [user_id]")
        return
    
    try:
        user_id = int(args[1])
        stats = get_user_stats(user_id)
        
        last_date = ""
        if stats.get('last_message'):
            last_date = datetime.fromisoformat(stats['last_message']).strftime('%d.%m.%Y %H:%M')
        
        text = f"""
👤 **СТАТИСТИКА ПОЛЬЗОВАТЕЛЯ {user_id}**

📝 Всего сообщений: {stats.get('total', 0)}
✅ Опубликовано: {stats.get('published', 0)}
📅 Последнее сообщение: {last_date or 'нет'}
        """
        await message.answer(text, parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        await message.answer("❌ Некорректный ID")

@dp.message(Command("ban"))
async def cmd_ban(message: types.Message):
    """Бан пользователя"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        await message.answer("❌ Использование: /ban [user_id] [причина]")
        return
    
    try:
        user_id = int(args[1])
        reason = args[2] if len(args) > 2 else "Нарушение правил"
        
        ban_user(user_id, message.from_user.id, reason)
        log_admin_action(message.from_user.id, 'ban', user_id, reason)
        
        try:
            await bot.send_message(user_id, f"⛔ Вы забанены.\nПричина: {reason}\nОбжалование: @ceo_chool65")
        except:
            pass
        
        await message.answer(f"✅ Пользователь {user_id} забанен. Причина: {reason}")
    except ValueError:
        await message.answer("❌ Некорректный ID")

@dp.message(Command("unban"))
async def cmd_unban(message: types.Message):
    """Разбан пользователя"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.answer("❌ Использование: /unban [user_id]")
        return
    
    try:
        user_id = int(args[1])
        unban_user(user_id)
        log_admin_action(message.from_user.id, 'unban', user_id)
        
        await message.answer(f"✅ Пользователь {user_id} разбанен")
    except ValueError:
        await message.answer("❌ Некорректный ID")

@dp.message(Command("help_admin"))
async def cmd_help_admin(message: types.Message):
    """Помощь по админским командам"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    text = """
📚 **ПОМОЩЬ ПО КОМАНДАМ**

**Экспорт данных:**
/export - все сообщения в Excel
/export_days 7 - за последние 7 дней

**Статистика:**
/stats - общая статистика
/user_stats 123456 - статистика пользователя

**Управление:**
/ban 123456 причина - заблокировать
/unban 123456 - разблокировать

**Модерация (кнопки в чате):**
✅ Опубликовать - пост уходит в канал
❌ Отклонить - пост не публикуется
📌 Взять в работу - закрепить пост за собой
🚫 Забанить автора - бан отправителя

📌 **Важно:** Все команды работают только в личке с ботом
    """
    await message.answer(text, parse_mode=ParseMode.MARKDOWN)

# ================== ФИЛЬТР ДЛЯ КОМАНД ==================
def is_command(message: types.Message) -> bool:
    """Проверяет, является ли сообщение командой"""
    return message.text and message.text.startswith('/')

# ================== ОБРАБОТЧИК СООБЩЕНИЙ ОТ ПОЛЬЗОВАТЕЛЕЙ ==================
@dp.message(lambda message: not is_command(message))
async def handle_user_message(message: types.Message):
    """Обработка входящих сообщений (НЕ КОМАНД)"""
    user_id = message.from_user.id
    
    # Дополнительная проверка на команды
    if message.text and message.text.startswith('/'):
        logger.debug(f"Игнорируем команду от {user_id}: {message.text}")
        return
    
    # Проверка бана
    if is_user_banned(user_id):
        ban_info = get_message_info(message.message_id)
        await message.answer("⛔ Вы заблокированы.")
        return
    
    # Собираем данные отправителя
    username = message.from_user.username or ""
    first_name = message.from_user.first_name or ""
    last_name = message.from_user.last_name or ""
    message_text = message.text or message.caption or ""
    message_type = "text"
    file_id = ""
    caption = message.caption or ""
    
    if message.photo:
        message_type = "photo"
        file_id = message.photo[-1].file_id
    elif message.video:
        message_type = "video"
        file_id = message.video.file_id
    elif message.video_note:  # ДОБАВЛЕНО: обработка кружков
        message_type = "video_note"
        file_id = message.video_note.file_id
    elif message.voice:
        message_type = "voice"
        file_id = message.voice.file_id
    elif message.document:
        message_type = "document"
        file_id = message.document.file_id
    elif message.audio:
        message_type = "audio"
        file_id = message.audio.file_id
    elif message.sticker:
        message_type = "sticker"
        file_id = message.sticker.file_id
    elif message.animation:
        message_type = "gif"
        file_id = message.animation.file_id
    
    # Сохраняем ВСЕ данные в БД
    if save_user_message(
        user_id, username, first_name, last_name,
        message_text, message_type, file_id, caption,
        message.message_id
    ):
        # Отправляем админам (только ID!)
        admin_text = f"📨 **Новое сообщение**\n"
        admin_text += f"🆔 ID: `{user_id}`\n"
        admin_text += f"📅 Время: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        
        sent_to_admins = 0
        
        for admin_id in ADMIN_IDS:
            try:
                if message.text:
                    sent_msg = await bot.send_message(
                        admin_id,
                        admin_text + f"📝 Текст:\n{message.text}",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=get_moderation_keyboard(message.message_id)
                    )
                elif message.photo:
                    sent_msg = await bot.send_photo(
                        admin_id,
                        message.photo[-1].file_id,
                        caption=admin_text + f"📝 Подпись: {caption}",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=get_moderation_keyboard(message.message_id)
                    )
                elif message.video:
                    sent_msg = await bot.send_video(
                        admin_id,
                        message.video.file_id,
                        caption=admin_text + f"📝 Подпись: {caption}",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=get_moderation_keyboard(message.message_id)
                    )
                elif message.video_note:  # ДОБАВЛЕНО: отправка кружков админам
                    # Отправляем видеосообщение (кружок)
                    sent_msg = await bot.send_video_note(
                        admin_id,
                        message.video_note.file_id,
                        reply_markup=get_moderation_keyboard(message.message_id)
                    )
                    # Отправляем отдельное сообщение с информацией (у кружков нет caption)
                    await bot.send_message(
                        admin_id,
                        admin_text + f"📹 **Видеосообщение (кружок)**",
                        parse_mode=ParseMode.MARKDOWN
                    )
                elif message.voice:
                    sent_msg = await bot.send_voice(
                        admin_id,
                        message.voice.file_id,
                        caption=admin_text,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=get_moderation_keyboard(message.message_id)
                    )
                elif message.document:
                    sent_msg = await bot.send_document(
                        admin_id,
                        message.document.file_id,
                        caption=admin_text + f"📝 Файл: {message.document.file_name}",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=get_moderation_keyboard(message.message_id)
                    )
                elif message.sticker:
                    sent_msg = await bot.send_sticker(
                        admin_id,
                        message.sticker.file_id,
                        reply_markup=get_moderation_keyboard(message.message_id)
                    )
                elif message.animation:
                    sent_msg = await bot.send_animation(
                        admin_id,
                        message.animation.file_id,
                        caption=admin_text,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=get_moderation_keyboard(message.message_id)
                    )
                else:
                    await bot.send_message(
                        admin_id,
                        admin_text + f"📝 [Неподдерживаемый тип сообщения]",
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=get_moderation_keyboard(message.message_id)
                    )
                
                sent_to_admins += 1
                
            except Exception as e:
                logger.error(f"Ошибка отправки админу {admin_id}: {e}")
        
        if sent_to_admins > 0:
            await message.answer("✅ Сообщение отправлено на модерацию!")
        else:
            await message.answer("⚠️ Временные проблемы, попробуйте позже")
    else:
        await message.answer("❌ Ошибка при сохранении сообщения")

# ================== ОБРАБОТЧИК КНОПОК ==================
@dp.callback_query(lambda c: c.data.startswith(('pub_', 'rej_', 'ban_', 'take_', 'noop')))
async def process_callback(callback: types.CallbackQuery, state: FSMContext):
    """Обработка нажатий на кнопки"""
    admin_id = callback.from_user.id
    
    if admin_id not in ADMIN_IDS:
        await callback.answer("⛔ Нет прав!", show_alert=True)
        return
    
    action, data = callback.data.split('_', 1)
    
    if action == 'noop':
        await callback.answer()
        return
    
    forward_id = int(data)
    msg_info = get_message_info(forward_id)
    
    if not msg_info:
        await callback.answer("❌ Сообщение не найдено", show_alert=True)
        return
    
    if action == 'take':
        # Взять в работу
        if msg_info['status'] == PostStatus.TAKEN.value:
            await callback.answer(f"❌ Уже в работе у {msg_info['taken_by']}", show_alert=True)
            return
        
        if update_message_status(forward_id, PostStatus.TAKEN, taken_by=admin_id):
            log_admin_action(admin_id, 'take', msg_info['user_id'])
            
            # Обновляем клавиатуру
            await callback.message.edit_reply_markup(
                reply_markup=get_moderation_keyboard(forward_id, admin_id)
            )
            await callback.answer("✅ Пост в работе!")
        else:
            await callback.answer("❌ Ошибка", show_alert=True)
    
    elif action == 'pub':
        # Публикация в канал
        try:
            # Пересылаем в канал
            forwarded = await bot.forward_message(
                chat_id=CHANNEL_ID,
                from_chat_id=admin_id,
                message_id=callback.message.message_id
            )
            
            if update_message_status(forward_id, PostStatus.PUBLISHED, channel_msg_id=forwarded.message_id):
                log_admin_action(admin_id, 'publish', msg_info['user_id'])
                
                # Уведомляем пользователя
                try:
                    await bot.send_message(
                        msg_info['user_id'],
                        "✅ Ваше сообщение опубликовано!"
                    )
                except:
                    pass
                
                # Обновляем сообщение
                await callback.message.edit_reply_markup(reply_markup=None)
                await callback.message.edit_text(
                    callback.message.text + "\n\n✅ **Опубликовано**",
                    parse_mode=ParseMode.MARKDOWN
                )
                await callback.answer("✅ Опубликовано!")
            else:
                await callback.answer("❌ Ошибка при обновлении статуса", show_alert=True)
            
        except Exception as e:
            logger.error(f"Ошибка публикации: {e}")
            await callback.answer(f"❌ Ошибка: {e}", show_alert=True)
    
    elif action == 'rej':
        # Отклонение
        if update_message_status(forward_id, PostStatus.REJECTED):
            log_admin_action(admin_id, 'reject', msg_info['user_id'])
            
            try:
                await bot.send_message(
                    msg_info['user_id'],
                    "❌ Ваше сообщение отклонено"
                )
            except:
                pass
            
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.message.edit_text(
                callback.message.text + "\n\n❌ **Отклонено**",
                parse_mode=ParseMode.MARKDOWN
            )
            await callback.answer("❌ Отклонено")
        else:
            await callback.answer("❌ Ошибка", show_alert=True)
    
    elif action == 'ban':
        # Бан (запросить причину)
        await state.set_state(AdminStates.waiting_for_ban_reason)
        await state.update_data(ban_user_id=msg_info['user_id'], ban_forward_id=forward_id, ban_message=callback.message)
        
        await callback.message.answer(
            f"✍️ Введите причину бана для пользователя {msg_info['user_id']}:"
        )
        await callback.answer()

# ================== ИСПРАВЛЕННЫЙ ОБРАБОТЧИК ПРИЧИНЫ БАНА С @ceo_chool65 ==================
@dp.message(AdminStates.waiting_for_ban_reason)
async def process_ban_reason(message: types.Message, state: FSMContext):
    """Обработка причины бана"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    data = await state.get_data()
    user_id = data.get('ban_user_id')
    forward_id = data.get('ban_forward_id')
    ban_message = data.get('ban_message')
    reason = message.text
    
    if user_id:
        # Баним пользователя
        ban_user(user_id, message.from_user.id, reason)
        log_admin_action(message.from_user.id, 'ban', user_id, reason)
        
        # Уведомляем забаненного пользователя с @ceo_chool65
        try:
            await bot.send_message(
                user_id, 
                f"⛔ Вы забанены.\nПричина: {reason}\nОбжалование: @ceo_chool65"
            )
        except:
            pass
        
        # Обновляем статус сообщения, если оно есть
        if forward_id:
            update_message_status(forward_id, PostStatus.REJECTED)
            
            # Обновляем сообщение с постом - добавляем информацию о бане
            if ban_message:
                try:
                    # Получаем текущий текст сообщения
                    current_text = ban_message.text or ban_message.caption or ""
                    
                    # Добавляем информацию о бане
                    new_text = f"{current_text}\n\n🚫 **Автор забанен**\nПричина: {reason}"
                    
                    # Обновляем сообщение (убираем кнопки и добавляем текст)
                    await ban_message.edit_text(
                        new_text,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=None
                    )
                except Exception as e:
                    logger.error(f"Ошибка при обновлении сообщения о бане: {e}")
        
        # Отправляем уведомление админу, который сделал бан
        await message.answer(f"✅ Пользователь {user_id} забанен. Причина: {reason}")
        
        # Уведомляем остальных админов
        for admin_id in ADMIN_IDS:
            if admin_id != message.from_user.id:  # Не отправляем тому, кто забанил
                try:
                    await bot.send_message(
                        admin_id,
                        f"🚫 Пользователь {user_id} забанен.\nПричина: {reason}\nАдмин: {message.from_user.id}"
                    )
                except Exception as e:
                    logger.error(f"Ошибка при уведомлении админа {admin_id}: {e}")
    
    await state.clear()

# ================== ЗАПУСК ==================
async def main():
    """Запуск бота"""
    if not init_db():
        logger.error("❌ Не удалось инициализировать базу данных")
        return
    
    # Проверяем подключение к Telegram
    try:
        me = await bot.get_me()
        logger.info(f"✅ Бот @{me.username} подключен")
        print(f"\n{'='*50}")
        print(f"✅ Бот @{me.username} успешно запущен!")
        print(f"📊 База данных: {DB_PATH}")
        print(f"👥 Администраторов: {len(ADMIN_IDS)}")
        print(f"📢 Канал ID: {CHANNEL_ID}")
        print(f"{'='*50}\n")
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к Telegram: {e}")
        print(f"\n❌ Ошибка подключения: {e}")
        return
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
