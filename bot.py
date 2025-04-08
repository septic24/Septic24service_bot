import pytz
import tzlocal
# Переопределяем tzlocal.get_localzone, чтобы возвращался pytz-объект
tzlocal.get_localzone = lambda: pytz.timezone("Europe/Kiev")

def patched_astimezone(tz):
    if tz is None:
        return None
    if not isinstance(tz, pytz.BaseTzInfo):
        try:
            if isinstance(tz, str):
                return pytz.timezone(tz)
            if hasattr(tz, 'key'):
                return pytz.timezone(tz.key)
            return pytz.timezone(str(tz))
        except Exception as e:
            raise TypeError('Only timezones from the pytz library are supported') from e
    return tz

import apscheduler.util
apscheduler.util.astimezone = patched_astimezone

import logging
import sys
import json
import os
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
)

print("Бот працює...")

# Токен бота и ID чата администратора
# TOKEN = "7747992449:AAEqWIUYRlhbdiwUnXqCYV3ODpNX9VUsed8"
# CHAT_ID = "2045410830"  # ID администратора


TOKEN = "7526376768:AAEX-zUQxObbLD5osWAF2Q0ieWP9yvoKBu4"
CHAT_ID = "5920866016"  # ID администратора

# Функция для генерации глобального номера заказа
def get_next_order_number(user_id):
    filename = "global_order_number.json"
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {"global_order": 0}
    else:
        data = {"global_order": 0}
    data["global_order"] += 1
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return data["global_order"]

# Команда /start – отправляем пользователю кнопку для открытия WebApp
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] Користувач {user.full_name} (ID: {user.id}) викликав /start")

    greeting_text = (
        "👋 Ласкаво просимо до Septic24!\n\n"
        "Ми надаємо професійні послуги з викачування вигрібних ям, септиків, каналізацій "
        "та вуличних туалетів по всій Україні.\n\n"
        "Натисніть кнопку нижче, щоб відкрити міні‑додаток і оформити замовлення:"
    )
    
    # URL веб‑приложения на GitHub Pages, с передачей user_id
    web_app_url = "https://applabua.github.io/Septic24service/?user_id=" + str(user.id)
    keyboard = [[InlineKeyboardButton("Замовити послугу♻️", web_app=WebAppInfo(url=web_app_url))]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    photo_url = "https://i.ibb.co/BH3bjrPP/IMG-9356.jpg"
    if update.message:
        await update.message.reply_photo(photo=photo_url, caption=greeting_text, reply_markup=reply_markup)

# Команда /orders – показать содержимое файла orders.txt (только для администратора)
async def orders_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != int(CHAT_ID):
        await update.message.reply_text("У вас немає доступу до історії замовлень.")
        return
    try:
        with open("orders.txt", "r", encoding="utf-8") as f:
            content = f.read()
        if not content.strip():
            content = "Історія замовлень порожня."
    except FileNotFoundError:
        content = "Файл з історією замовлень не знайдено."
    await update.message.reply_text(content)

# Новая команда /users – показать список уникальных UserID заказчиков (только для администратора)
async def users_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != int(CHAT_ID):
        await update.message.reply_text("У вас немає доступу до цієї команди.")
        return
    try:
        with open("orders.txt", "r", encoding="utf-8") as f:
            content = f.read()
        user_ids = set()
        for line in content.splitlines():
            if line.startswith("UserID:"):
                uid = line.split("UserID:")[1].strip()
                if uid:
                    user_ids.add(uid)
        if user_ids:
            msg = "Список користувачів:\n" + "\n".join(user_ids)
        else:
            msg = "Користувачі відсутні."
    except FileNotFoundError:
        msg = "Файл з історією замовлень не знайдено."
    await update.message.reply_text(msg)

# Обработчик данных, отправленных через Telegram.WebApp.sendData
async def webapp_data_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.web_app_data:
        data_str = update.web_app_data.data
        try:
            order = json.loads(data_str)
        except Exception:
            order = {}

        # Генерируем глобальный номер заказа и рассчитываем номер по схеме 1-5
        order_number = get_next_order_number(order.get('user_id', 'unknown'))
        displayed_order = order_number % 5
        if displayed_order == 0:
            displayed_order = 5

        # Формируем текст заказа для администратора, включая номер заказа
        finalMsg = f"Номер замовлення: {displayed_order}/5\nНове замовлення від Septic24:\n"
        finalMsg += f"Ім'я: {order.get('name','')}\n"
        finalMsg += f"Телефон: {order.get('phone','')}\n"
        finalMsg += f"Область: {order.get('region','')}\n"
        finalMsg += f"Адреса: {order.get('address','')}\n"
    
        serviceIndex = order.get('serviceIndex')
        if serviceIndex is not None:
            servicesTitles = [
                "Викачка вигрібних ям",
                "Викачка мулу чи піску",
                "Викачка септика",
                "Прочистка труб",
                "Викачка туалету"
            ]
            if 0 <= serviceIndex < len(servicesTitles):
                finalMsg += f"Послуга: {servicesTitles[serviceIndex]}\n"
            if serviceIndex == 3:
                finalMsg += f"Довжина труб: {order.get('length','?')} м\n"
                finalMsg += f"Діаметр труб: {order.get('diameter','?')} мм\n"
            else:
                finalMsg += f"Об'єм ємності: {order.get('volume','?')} м³\n"
                finalMsg += f"Відстань від парковки до ємності: {order.get('distance','?')} м\n"
        
        coords = order.get('coords')
        if coords and 'x' in coords and 'y' in coords:
            lat = coords['y']
            lon = coords['x']
            finalMsg += f"Геолокація: {lat:.5f}, {lon:.5f}\n"
            finalMsg += f"OpenStreetMap: https://www.openstreetmap.org/?mlat={lat}&mlon={lon}\n"

        if order.get('user_id'):
            finalMsg += f"UserID: {order.get('user_id')}\n"

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("orders.txt", "a", encoding="utf-8") as f:
            f.write(f"[{now_str}]\n{finalMsg}\n\n")

        # Отправляем заказ адміну
        await context.bot.send_message(chat_id=CHAT_ID, text=finalMsg)

        # Дублируем заказ и отправляем его также пользователю
        try:
            if str(order.get('user_id')).isdigit():
                await context.bot.send_message(chat_id=int(order.get('user_id')), text=finalMsg)
        except Exception:
            pass

        # Вычисляем бонус по номеру заказа и формируем красивое сообщение
        if displayed_order == 5:
            bonus_text = ("Ваше замовлення 5/5 оформлено успішно! Дякуємо за ваше замовлення. "
                          "Очікуйте на дзвінок. 📞\n\n🎉 За кожне замовлення Ви отримуєте 2% знижку, "
                          "а кожне 5‑те замовлення – 10% знижку!")
        else:
            bonus_text = (f"Ваше замовлення {displayed_order}/5 оформлено успішно! Дякуємо за ваше замовлення. "
                          "Очікуйте на дзвінок. 📞\n\n💧 За кожне замовлення Ви отримуєте 2% знижку, "
                          "а кожне 5‑те замовлення – 10% знижку!")
        # Отправляем бонусное сообщение и адміну, и пользователю
        await context.bot.send_message(chat_id=CHAT_ID, text=bonus_text)
        try:
            if str(order.get('user_id')).isdigit():
                await context.bot.send_message(chat_id=int(order.get('user_id')), text=bonus_text)
        except Exception:
            pass

        if update.effective_message:
            await update.effective_message.reply_text("Ваше замовлення збережено!\nОчікуйте на дзвінок.")

        print("Отримано замовлення:", finalMsg)

def main() -> None:
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("orders", orders_history))
    application.add_handler(CommandHandler("users", users_list))
    application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp_data_handler))
    application.run_polling()

if __name__ == "__main__":
    main()
