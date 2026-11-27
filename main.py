import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.filters.command import Command
from aiogram.types import InlineQuery, InlineQueryResultPhoto
from aiogram.exceptions import TelegramBadRequest
from supabase import create_client, Client

from handlers import router as channel_router
from services.db import search_memes
from services.selector import get_random_meme
from utils.logger import logger
from utils.settings import settings


async def main():
    """Initializes the bot, database client, handlers, and starts polling."""
    settings.load_from_dotenv()

    # Если в .env указан прокси, создаем сессию с ним, иначе обычную
    session = AiohttpSession(proxy=settings.PROXY_URL) if settings.PROXY_URL else None
    bot = Bot(token=settings.TOKEN, session=session)
    dp = Dispatcher()

    # Подключаемся к базе данных Supabase и передаем клиент в диспетчер
    supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    dp["supabase"] = supabase

    # Подключаем роутер, который следит за новыми постами в канале
    dp.include_router(channel_router)

    @dp.message(Command("start"))
    async def cmd_start(message: types.Message):
        """Sends a welcome message with bot usage instructions."""
        user = message.from_user
        logger.info(f"User {user.id} (@{user.username}) sent /start")

        await message.answer(
            "Привет! Бот активен и следит за каналом.\n\n"
            "• /random — прислать случайный мем\n"
            "• `@finder_mem_bot <слово>` в любом чате — поиск по мемам\n"
            "• `@finder_mem_bot random` — случайный мем в инлайн-режиме"
        )

    @dp.message(Command("random"))
    async def cmd_random(message: types.Message):
        """Fetches and sends a random meme to the chat."""
        user = message.from_user
        logger.info(f"User {user.id} (@{user.username}) requested /random")

        # Вызываем синхронную функцию БД в отдельном потоке, чтобы не тормозить бота
        meme = await asyncio.to_thread(get_random_meme, supabase)
        if not meme or not meme.get("photo_url"):
            logger.warning(f"No memes found in DB for user {user.id}")
            await message.answer("В базе пока нет мемов.")
            return

        logger.info(f"Sending random meme #{meme['id']} to user {user.id}")
        await message.answer_photo(photo=meme["photo_url"])

    @dp.inline_query()
    async def handle_inline_query(inline_query: InlineQuery):
        """Handles inline search requests from any Telegram chat."""
        user = inline_query.from_user
        query = inline_query.query.strip().lower()

        # Если пользователь просто ввел имя бота без текста — возвращаем пустой список
        if not query:
            try:
                await inline_query.answer([], cache_time=5, is_personal=True)
            except TelegramBadRequest:
                pass
            return

        logger.info(f"Inline query from {user.id} (@{user.username}): '{query}'")

        # Обработка запроса случайного мема в инлайн-режиме
        if query in ("random", "рандом"):
            meme = await asyncio.to_thread(get_random_meme, supabase)
            results = []
            if meme and meme.get("photo_url"):
                url = meme["photo_url"].strip()
                results.append(
                    InlineQueryResultPhoto(
                        id=str(meme["id"]),
                        photo_url=url,
                        thumbnail_url=url,
                    )
                )
                logger.info(f"Returning inline random meme #{meme['id']} for user {user.id}")
            try:
                await inline_query.answer(results, cache_time=1, is_personal=True)
            except TelegramBadRequest:
                pass
            return

        # Поиск подходящих мемов в базе по ключевым словам
        items = await asyncio.to_thread(search_memes, supabase, query)
        logger.info(f"Found {len(items)} memes for query '{query}' (user {user.id})")

        # Формируем список карточек с картинками для выдачи в Telegram (максимум 50)
        results = [
            InlineQueryResultPhoto(
                id=str(item["id"]),
                photo_url=item["photo_url"].strip(),
                thumbnail_url=item["photo_url"].strip(),
            )
            for item in items[:50]
            if item.get("photo_url")
        ]

        try:
            await inline_query.answer(results, cache_time=30, is_personal=True)
        except TelegramBadRequest as e:
            logger.warning(f"Inline query error for user {user.id}: {e}")

    logger.info("Starting bot...")
    # Удаляем старые накопившиеся апдейты и запускаем опрос серверов Telegram
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
