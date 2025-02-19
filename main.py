import os
import uuid
import logging
from telegram import Update, InputFile, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

#импорты из других файлов
from bot_db import check_rate_limit #функция проверяющая количество запросов и файл с базой данных о пользователях
from dictionary import translations #словарь со всем текстом на двух яызках
from task_generations import generate_markdown, markdown_to_pdf #функции генерации файлов

TELEGRAM_TOKEN = ""  #твой токен

# Настроим логирование
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()]
)

# Функция для получения языка пользователя (по умолчанию "en")
def get_user_language(context):
    return context.user_data.get("language", "en")

# Кнопки выбора языка
def get_language_keyboard():
    keyboard = [
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
         InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Кнопки меню
def get_menu_keyboard(lang):
    keyboard = [
        [InlineKeyboardButton("📄 Generate Math Problems", callback_data="menu_generate") if lang == "en" else 
         InlineKeyboardButton("📄 Сгенерировать задачи", callback_data="menu_generate")],
        [InlineKeyboardButton("🌍 Change Language", callback_data="menu_language") if lang == "en" else 
         InlineKeyboardButton("🌍 Сменить язык", callback_data="menu_language")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Команда /start (первый запуск – только выбор языка)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        translations["start"]["en"] if get_user_language(context) == "en" else translations["start"]["ru"],
        reply_markup=get_language_keyboard()
    )

# Обработчик выбора языка (по нажатию кнопки)
async def set_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = "en" if query.data == "lang_en" else "ru"

    context.user_data["language"] = lang
    await query.answer()
    await query.edit_message_text(translations["language_set"][lang],reply_markup=None)

    # Обновляем команды Telegram
    await context.bot.set_my_commands([
        BotCommand("menu", "Open main menu" if lang == "en" else "Открыть меню"),
        BotCommand("generate", "Generate math problems" if lang == "en" else "Сгенерировать математические задачи"),
        BotCommand("language", "Change bot language" if lang == "en" else "Сменить язык бота")
    ])

    # Отправляем меню после выбора языка
    await query.message.reply_text(
        translations["menu"][lang],
        parse_mode="Markdown",
        reply_markup=get_menu_keyboard(lang)
    )

# Команда /menu (открывает меню команд)
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = get_user_language(context)
    await update.message.reply_text(
        translations["menu"][lang],
        parse_mode="Markdown",
        reply_markup=get_menu_keyboard(lang)
    )

# Обработчик нажатий в меню
async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    lang = get_user_language(context)

    if query.data == "menu_generate":
        await query.answer()
        await query.message.reply_text(translations["menu_generate"][lang])

    elif query.data == "menu_language":
        await query.answer()
        await query.message.reply_text(
            translations["menu_language"][lang],
            reply_markup=get_language_keyboard()
        )

# Команда /generate
async def generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    lang = get_user_language(context)

    # Проверяем лимит перед генерацией
    if not check_rate_limit(chat_id):
        await update.message.reply_text(translations["exceeded_limit"][lang])
        return

    query = ' '.join(context.args) if context.args else None
    if not query:
        await update.message.reply_text(translations["provide_topic"][lang])
        return

    generated_markdown = generate_markdown(query)
    if not generated_markdown:
        await update.message.reply_text(translations["generation_error"][lang])
        return

    filename = f"output_{uuid.uuid4().hex}.pdf"
    pdf_file = markdown_to_pdf(generated_markdown, filename)

    if pdf_file and os.path.exists(pdf_file):
        try:
            with open(pdf_file, "rb") as f:
                await update.message.reply_document(document=InputFile(f), filename=pdf_file)
            os.remove(pdf_file)
        except Exception as e:
            logging.error(f"Ошибка при отправке PDF: {e}")
            await update.message.reply_text(translations["sending_error"][lang])
    else:
        await update.message.reply_text(translations["generation_error"][lang])

# Запуск бота
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))  # /start – выбираем язык
    app.add_handler(CommandHandler("menu", menu))  # /menu – открывает меню
    app.add_handler(CommandHandler("generate", generate))  # /generate – генерация задач
    app.add_handler(CallbackQueryHandler(set_language_callback, pattern="^lang_"))  # Выбор языка
    app.add_handler(CallbackQueryHandler(menu_callback, pattern="^menu_"))  # Клики в меню

    logging.info("✅ Бот запущен...")
    app.run_polling()
