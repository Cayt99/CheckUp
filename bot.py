from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
from datetime import datetime, timedelta
import dateparser


class ScheduleBot:
    def __init__(self, token, admin_chat_id):
        self.application = Application.builder().token(token).build()
        self.admin_chat_id = admin_chat_id  # ID группы администраторов

        # Регистрация команд и обработчиков
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.collect_user_data))

        # Для сохранения состояния выбора
        self.user_data = {}

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Стартовый шаг: запрос ФИО"""
        user_id = update.effective_user.id
        self.user_data[user_id] = {}
        await update.message.reply_text("Введите ваше ФИО:")

    async def collect_user_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Сбор ФИО, номера телефона и даты"""
        user_id = update.effective_user.id

        # Если бот ждёт ручной ввод даты
        if self.user_data.get(user_id, {}).get('awaiting_manual_date', False):
            raw_date = update.message.text
            parsed_date = dateparser.parse(raw_date)

            if parsed_date:
                self.user_data[user_id]['date'] = parsed_date.strftime("%Y-%m-%d")
                self.user_data[user_id]['awaiting_manual_date'] = False
                await update.message.reply_text(f"Вы выбрали дату: {self.user_data[user_id]['date']}. Теперь выберите время:")
                return await self.show_time_selection(update)
            else:
                await update.message.reply_text("Не удалось распознать дату. Попробуйте ещё раз (например, 'декабрь 25' или '12 25').")
                return

        if "fio" not in self.user_data[user_id]:
            self.user_data[user_id]['fio'] = update.message.text
            await update.message.reply_text("Введите ваш номер телефона:")
        elif "phone" not in self.user_data[user_id]:
            self.user_data[user_id]['phone'] = update.message.text
            await self.show_date_selection(update)

    async def show_date_selection(self, update: Update):
        """Выбор даты"""
        today = datetime.now().strftime("%Y-%m-%d")
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        keyboard = [
            [
                InlineKeyboardButton(f"Сегодня ({today})", callback_data=f"date_{today}"),
                InlineKeyboardButton(f"Завтра ({tomorrow})", callback_data=f"date_{tomorrow}")
            ],
            [
                InlineKeyboardButton("Указать вручную", callback_data="date_manual")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Выберите дату:", reply_markup=reply_markup)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатия кнопок"""
        query = update.callback_query
        user_id = query.from_user.id
        await query.answer()  # Подтверждение нажатия кнопки

        if query.data.startswith("date_"):
            selected_date = query.data.split("_")[1]
            if selected_date == "manual":
                await query.edit_message_text("Введите желаемую дату в любом формате (например, 'декабрь 25' или '12 25'):")
                self.user_data[user_id]['awaiting_manual_date'] = True
            else:
                self.user_data[user_id]['date'] = selected_date
                await query.edit_message_text(f"Вы выбрали дату: {selected_date}. Теперь выберите время:")
                await self.show_time_selection(query)
        elif query.data.startswith("time_"):
            # Обработка выбора времени
            time = query.data.split("_")[1]
            self.user_data[user_id]['time'] = time
            await self.show_role_selection(query)
        elif query.data.startswith("role_"):
            # Обработка выбора должности
            role = query.data.split("_")[1]
            self.user_data[user_id]['role'] = role
            await self.send_to_group(query, context)

    async def show_time_selection(self, update_or_query):
        """Выбор времени"""
        keyboard = [
            [
                InlineKeyboardButton("07:00 - 17:00", callback_data=f"time_07:00-17:00"),
                InlineKeyboardButton("08:00 - 18:00", callback_data=f"time_08:00-18:00")
            ],

            [
                InlineKeyboardButton("09:00 - 19:00", callback_data=f"time_09:00-19:00"),
                InlineKeyboardButton("10:00 - 20:00", callback_data=f"time_10:00-20:00")  # Новый промежуток
            ],

            [
                InlineKeyboardButton("11:00 - 21:00", callback_data=f"time_11:00-21:00"),
                InlineKeyboardButton("11:30 - 21:30", callback_data=f"time_11:30-21:30")  # Новый промежуток
            ],

            [
                InlineKeyboardButton("12:00 - 22:00", callback_data=f"time_12:00-22:00"),
            ] 
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if isinstance(update_or_query, Update):
            await update_or_query.message.reply_text("Выберите время:", reply_markup=reply_markup)
        else:
            await update_or_query.edit_message_text("Выберите время:", reply_markup=reply_markup)

    async def show_role_selection(self, query):
        """Выбор должности"""
        keyboard = [
            [
                InlineKeyboardButton("Продавец-кассир", callback_data="role_Кассир"),
                InlineKeyboardButton("Продавец-консультант", callback_data="role_Консультант")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите должность:", reply_markup=reply_markup)

    async def send_to_group(self, query, context):
        """Отправка заявки в группу"""
        user_id = query.from_user.id
        user_data = self.user_data[user_id]
        summary = (
            f"Заявка от сотрудника:\n"
            f"ФИО: {user_data['fio']}\n"
            f"Телефон: {user_data['phone']}\n"
            f"Дата: {user_data['date']}\n"
            f"Время: {user_data['time']}\n"
            f"Должность: {user_data['role']}"
        )

        # Отправка в группу
        await context.bot.send_message(chat_id=self.admin_chat_id, text=summary)

        # Уведомление пользователя
        await query.edit_message_text("Ваша заявка успешно отправлена. Спасибо!")

    def run(self):
        """Запуск бота"""
        print("Бот запущен...")
        self.application.run_polling()


if __name__ == "__main__":
    TOKEN = "7224409666:AAGzwOgAQlhC5Poa4kfVIdtchjqVPdn1Szs"  
    ADMIN_CHAT_ID = -4705494121  
    bot = ScheduleBot(TOKEN, ADMIN_CHAT_ID)
    bot.run()