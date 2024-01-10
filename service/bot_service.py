import configparser
import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ContentType as CT
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

from model.user_model import UserModel
from repo import user_repo, queue_repo, message_repo
from states.chat_states import ChatStates
from states.profile_states import ProfileStates

config = configparser.ConfigParser()
config.read('tg.ini')

bot = Bot(config["tg"]["token"])
dp = Dispatcher(storage=MemoryStorage())

logging.basicConfig(level=logging.INFO)


@dp.message(Command('start'))
async def start(message: Message,
                state: FSMContext):
    """
    /start
    If it's new user - save to db and start filling the profile
    """
    chat_id: int = message.chat.id
    if not user_repo.user_exists(chat_id):
        user_repo.create_user(chat_id=chat_id,
                              user_id=message.from_user.id,
                              username=message.from_user.username)
        await message.answer("Привіт, вітаю тебе в боті анонімного спілкування.")
        await fill_profile(message)
    else:
        user: UserModel = user_repo.get_user_by_chat_id(message.chat.id)

        # if was in queue:
        queue_repo.remove_user_from_queue(message.chat.id)

        # If was connected with:
        if user.connected_with != 0:
            # Disconnect
            connected_user: UserModel = user_repo.get_user_by_chat_id(chat_id=user.connected_with)
            user_repo.update_user_connected_with(chat_id=user.chat_id,
                                                 connected_with=0)
            user_repo.update_user_connected_with(chat_id=user.connected_with,
                                                 connected_with=0)

            # Process remote user
            await bot.send_message(chat_id=connected_user.chat_id,
                                   text="😔 Діалог припинено")
            await send_user_profile(chat_id=connected_user.chat_id)
            await clear_state(chat_id=user.connected_with,
                              user_id=connected_user.user_id)

        # Send user profile
        await state.clear()
        await send_user_profile(chat_id=user.chat_id)


async def send_user_profile(chat_id: int):
    """
    Like a main menu of bot
    From here you can see or change your profile, start chatting
    """
    user: UserModel = user_repo.get_user_by_chat_id(chat_id)

    fill_profile_button = InlineKeyboardButton(text="👤 Заповинти профіль наново", callback_data="change-profile")
    start_chatting_button = InlineKeyboardButton(text="💌 Пошук співрозмовника", callback_data="search-menu")
    rules_button = InlineKeyboardButton(text="📕 Правила", callback_data="rules")
    markup = InlineKeyboardMarkup(inline_keyboard=[[fill_profile_button], [start_chatting_button], [rules_button]])

    await bot.send_message(chat_id=chat_id,
                           text=user.get_profile(),
                           reply_markup=markup)


async def fill_profile(message: Message):
    """
    Starts the chain of filling the profile
    1) Asks the gender
    2) Asks the age
    3) Asks the name
    """
    man_button = InlineKeyboardButton(text="Я хлопець👨", callback_data="MALE")
    woman_button = InlineKeyboardButton(text="Я дівчина👩", callback_data="FEMALE")
    keyboard_markup = InlineKeyboardMarkup(row_width=2, inline_keyboard=[list([man_button, woman_button])])

    await message.answer(
        text="Вибери свою стать",
        reply_markup=keyboard_markup)


@dp.callback_query(lambda c: c.data in ['MALE', 'FEMALE'])
async def process_gender_callback(callback_query: CallbackQuery,
                                  state: FSMContext):
    """ Changes the age of user to db, prepare state to change age """
    sex = callback_query.data
    chat_id = callback_query.message.chat.id

    user_repo.update_user_sex(sex, chat_id)
    await callback_query.answer()
    await callback_query.message.answer("Введи свій вік")
    await bot.delete_message(chat_id=callback_query.message.chat.id,
                             message_id=callback_query.message.message_id)

    await state.set_state(ProfileStates.ask_age)


@dp.message(ProfileStates.ask_age)
async def process_ask_age(message: Message,
                          state: FSMContext):
    age = message.text
    try:
        age = int(age)
        if age < 0 or age > 100:
            raise ValueError("Вибраний вік поза межами")
    except ValueError:
        return await message.answer("Будь ласка введіть Ваш реальний вік")

    user_repo.update_user_age(age=age,
                              chat_id=message.chat.id)

    await message.answer("Як мені тебе називати?")
    await state.set_state(ProfileStates.ask_name)


@dp.message(ProfileStates.ask_name)
async def process_ask_name(message: Message,
                           state: FSMContext):
    name: str = message.text
    user_repo.update_user_name(name, message.chat.id)
    await state.clear()
    await send_user_profile(chat_id=message.chat.id)


@dp.callback_query(lambda c: c.data == 'change-profile')
async def process_change_profile(callback_query: CallbackQuery):
    """ On pressing change profile button """
    await bot.delete_message(chat_id=callback_query.message.chat.id,
                             message_id=callback_query.message.message_id)
    await fill_profile(callback_query.message)


@dp.callback_query(lambda c: c.data == 'profile')
async def process_send_profile(callback_query: CallbackQuery):
    """ On pressing my profile button """
    await bot.delete_message(chat_id=callback_query.message.chat.id,
                             message_id=callback_query.message.message_id)
    await send_user_profile(chat_id=callback_query.message.chat.id)


@dp.callback_query(lambda c: c.data == 'rules')
async def process_send_rules(callback_query: CallbackQuery):
    """ On pressing rules button """
    await bot.delete_message(chat_id=callback_query.message.chat.id,
                             message_id=callback_query.message.message_id)

    fill_profile_button = InlineKeyboardButton(text="👤 Мій профіль", callback_data="profile")
    start_chatting_button = InlineKeyboardButton(text="💌 Пошук співрозмовника", callback_data="search-menu")
    markup = InlineKeyboardMarkup(inline_keyboard=[[fill_profile_button], [start_chatting_button]])

    await callback_query.message.answer(
        text="""
📌Правила спілкування в Анонімному чаті:

1. Будь-які згадки про психоактивні речовини (наркотики).
2. Дитяча порнографія ("ЦП").
3. Шахрайство (Scam).
4. Будь-яка реклама, спам.
5. Продаж будь-чого (наприклад - продаж інтимних фотографій, відео).
6. Будь-які дії, які порушують правила Telegram.
7. Образлива поведінка.

☀️ Бажаємо успіху та приємного спілкування 🤗
""",

        # Функція захисту від фотографій, відео, стікерів 🔞
        # ✖️ Вимкнути /off
        # ✅ Увімкнути /on

        reply_markup=markup
    )


@dp.callback_query(lambda c: c.data == 'search-menu')
async def process_start_searching(callback_query: CallbackQuery):
    """
    Returns menu with search parameters
    1) Search men
    2) Search women
    3) Random search
    """
    message = "❤️‍🔥 Виберіть стать співрозмовника"
    man_button = InlineKeyboardButton(text="👨 Хлопець", callback_data='SEARCH_MALE')
    woman_button = InlineKeyboardButton(text="👩 Дівчина", callback_data='SEARCH_FEMALE')
    random_button = InlineKeyboardButton(text="👫 Випадковий діалог", callback_data='SEARCH_RANDOM')
    markup = InlineKeyboardMarkup(inline_keyboard=[[man_button, woman_button], [random_button]])
    await callback_query.message.answer(text=message,
                                        reply_markup=markup)
    await bot.delete_message(chat_id=callback_query.message.chat.id,
                             message_id=callback_query.message.message_id)


@dp.callback_query(lambda c: c.data.startswith('SEARCH_'))
async def process_search(callback_query: CallbackQuery,
                         state: FSMContext):
    """
    To process searching just create new user_queue and save it to db
    Queue Service will have done all work to match dialogs
    """
    user: UserModel = user_repo.get_user_by_chat_id(chat_id=callback_query.message.chat.id)
    sex_to_search: str = callback_query.data.split('_')[1]
    queue_repo.add_user_to_queue(chat_id=user.chat_id,
                                 user_id=user.user_id,
                                 sex=user.sex,
                                 sex_to_search=sex_to_search)

    cancel_button = InlineKeyboardButton(text="Відмінити пошук",
                                         callback_data="cancel-search")
    markup = InlineKeyboardMarkup(inline_keyboard=[[cancel_button]])

    await callback_query.message.answer(text="🔍 Почекайте, шукаю...",
                                        reply_markup=markup)
    await bot.delete_message(chat_id=callback_query.message.chat.id,
                             message_id=callback_query.message.message_id)
    await state.set_state(ChatStates.search)


@dp.callback_query(lambda c: c.data == 'cancel-search')
async def process_cancel_search(callback_query: CallbackQuery,
                                state: FSMContext):
    queue_repo.remove_user_from_queue(chat_id=callback_query.message.chat.id)
    await state.clear()
    await callback_query.answer(text="❌ Пошук відмінено")
    await bot.delete_message(chat_id=callback_query.message.chat.id,
                             message_id=callback_query.message.message_id)
    await send_user_profile(chat_id=callback_query.message.chat.id)


async def set_state(chat_id: int,
                    user_id: int,
                    custom_state: State):
    state = dp.fsm.resolve_context(
        bot=bot,
        chat_id=chat_id,
        user_id=user_id
    )
    await state.set_state(custom_state)


async def clear_state(chat_id: int,
                      user_id: int):
    state = dp.fsm.resolve_context(
        bot=bot,
        chat_id=chat_id,
        user_id=user_id
    )
    await state.clear()


@dp.message(Command('stop'))
async def process_stop_chatting(message: Message,
                                state: FSMContext):
    """ Stop messaging """
    user: UserModel = user_repo.get_user_by_chat_id(chat_id=message.chat.id)
    user_repo.update_user_connected_with(chat_id=user.chat_id,
                                         connected_with=0)
    user_repo.update_user_connected_with(chat_id=user.connected_with,
                                         connected_with=0)

    connected_user = user_repo.get_user_by_chat_id(chat_id=user.connected_with)

    # Process user
    await send_user_profile(chat_id=message.chat.id)
    await state.clear()

    # Process remote user
    await bot.send_message(chat_id=connected_user.chat_id,
                           text="😔 Діалог припинено")
    await send_user_profile(chat_id=connected_user.chat_id)
    await clear_state(chat_id=user.connected_with,
                      user_id=connected_user.user_id)

@dp.message(ChatStates.chatting)
async def process_chatting(message: Message):
    """ There is chatting here """

    match message.content_type:
        case CT.TEXT:
            user: UserModel = user_repo.get_user_by_chat_id(chat_id=message.chat.id)
            await bot.send_message(chat_id=user.connected_with,
                                   text=message.text)
            message_repo.save_message(chat_id_from=user.chat_id,
                                      chat_id_to=user.connected_with,
                                      message=message.text,
                                      date=datetime.now())
        case CT.PHOTO:
            user: UserModel = user_repo.get_user_by_chat_id(chat_id=message.chat.id)
            await process_photo(message=message,
                                user=user)
        case CT.STICKER:
            user: UserModel = user_repo.get_user_by_chat_id(chat_id=message.chat.id)

            await bot.send_sticker(
                chat_id=user.connected_with,
                sticker=message.sticker.file_id
            )


@dp.message()
async def process_unexpected(message: Message,
                             state: FSMContext):
    """
    Sometimes connection may be lost.
    So if in db we connected, lets enable it again
    """
    match message.content_type:
        case CT.TEXT:
            """ Handling text """
            user: UserModel = user_repo.get_user_by_chat_id(message.chat.id)
            if user.connected_with != 0:
                await state.set_state(ChatStates.chatting)

                await bot.send_message(chat_id=user.connected_with,
                                       text=message.text)
                return

            """ Default message """
            await bot.send_message(chat_id=user.chat_id,
                                   text="""
Я тебе не зовсім розумію
Тикай /start, якщо щось пішло не так
""")
        case CT.PHOTO:
            """ Handling photo """
            user: UserModel = user_repo.get_user_by_chat_id(chat_id=message.chat.id)

            await process_photo(message=message,
                                user=user)


async def process_photo(message: Message,
                        user: UserModel):
    """
    Current method process photo during the chatting
    It Saves photo to db and if user connected with someone, sends photo
    """
    try:
        directory_name = f'./images/{message.chat.id}'
        file_name: str = f'{directory_name}/{message.photo[1].file_id}.jpg'
        if not os.path.exists(directory_name):
            os.makedirs(directory_name)
        file = await bot.get_file(message.photo[-1].file_id)
        file_path = file.file_path
        await bot.download_file(file_path, file_name)
        if user.connected_with != 0:
            await bot.send_photo(chat_id=user.connected_with,
                                 photo=message.photo[-1].file_id,
                                 caption=message.text)
    except():
        pass


async def send_message_connected_with(chat_id: int):
    user: UserModel = user_repo.get_user_by_chat_id(chat_id=chat_id)
    connected_user: UserModel = user_repo.get_user_by_chat_id(chat_id=user.connected_with)
    await bot.send_message(text=
                           f"""
🥰 Знайшли для тебе когось! 
{'👨' if connected_user.sex == 'MALE' else '👩'} - {connected_user.name} - {connected_user.age}
Приємного спілкування!

/stop - щоб закінчити діалог
        """,
                           chat_id=user.chat_id)


async def init_bot():
    await dp.start_polling(bot)
