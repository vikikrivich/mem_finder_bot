import asyncio
from io import BytesIO
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from supabase import create_client, Client

from handlers import extract_tags
from utils.logger import logger
from utils.settings import settings

# Диапазон ID сообщений из канала, которые нужно загрузить в базу
START_MSG_ID = 1
END_MSG_ID = 70
BUCKET_NAME = "memes"


async def run_parser():
    """Fetches historical posts from the channel and uploads memes to Supabase."""
    settings.load_from_dotenv()

    if not all([settings.TOKEN, settings.SUPABASE_URL, settings.SUPABASE_KEY, settings.CHANNEL_ID, settings.MY_TELEGRAM_ID]):
        logger.error("Missing required environment variables in .env")
        return

    session = AiohttpSession(proxy=settings.PROXY_URL, timeout=60) if settings.PROXY_URL else None
    bot = Bot(token=settings.TOKEN, session=session)
    supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

    logger.info(f"Parsing messages from {START_MSG_ID} to {END_MSG_ID}...")
    saved_count = 0

    try:
        for msg_id in range(START_MSG_ID, END_MSG_ID + 1):
            for attempt in range(3):
                forwarded = None
                try:
                    # Пересылаем пост себе в личку, так как Bot API не умеет читать историю канала напрямую
                    forwarded = await bot.forward_message(
                        chat_id=settings.MY_TELEGRAM_ID,
                        from_chat_id=settings.CHANNEL_ID,
                        message_id=msg_id
                    )

                    # Сохраняем только если в посте есть картинка и текстовая подпись
                    if forwarded.photo and forwarded.caption and forwarded.caption.strip():
                        caption = forwarded.caption
                        tags = extract_tags(caption)
                        best_photo = forwarded.photo[-1]
                        file_path = f"{msg_id}.jpg"

                        buffer = BytesIO()
                        await bot.download(best_photo, destination=buffer)
                        image_bytes = buffer.getvalue()

                        # Загружаем фото в хранилище и получаем ссылку
                        await asyncio.to_thread(
                            lambda: supabase.storage.from_(BUCKET_NAME).upload(
                                path=file_path,
                                file=image_bytes,
                                file_options={"content-type": "image/jpeg", "upsert": "true"},
                            )
                        )
                        public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(file_path)

                        # Сохраняем запись в таблицу БД
                        data_payload = {
                            "channel_message_id": msg_id,
                            "caption": caption,
                            "tags": tags,
                            "photo_url": public_url,
                        }
                        await asyncio.to_thread(
                            lambda: supabase.table("memes").upsert(
                                data_payload,
                                on_conflict="channel_message_id"
                            ).execute()
                        )

                        saved_count += 1
                        logger.info(f"[{saved_count}] Saved meme #{msg_id}")
                        # Небольшая пауза, чтобы Telegram не заблокировал за частые запросы
                        await asyncio.sleep(0.6)
                    else:
                        await asyncio.sleep(0.05)

                    break

                except TelegramBadRequest:
                    # Пост с таким ID удален или является сервисным — идем дальше
                    await asyncio.sleep(0.05)
                    break
                except TelegramRetryAfter as e:
                    # Если Telegram просит подождать из-за флуд-контроля — ждем указанное время
                    logger.warning(f"Flood control: sleeping for {e.retry_after}s")
                    await asyncio.sleep(e.retry_after)
                except Exception as e:
                    logger.warning(f"Attempt {attempt + 1}/3 failed for #{msg_id}: {e}")
                    await asyncio.sleep(2)
                finally:
                    # Обязательно удаляем пересланное сообщение из своей лички, чтобы не засорять чат
                    if forwarded:
                        try:
                            await bot.delete_message(
                                chat_id=settings.MY_TELEGRAM_ID,
                                message_id=forwarded.message_id
                            )
                        except Exception:
                            pass
    finally:
        await bot.session.close()
        logger.info(f"Parsing finished! Saved: {saved_count} memes.")


if __name__ == "__main__":
    asyncio.run(run_parser())
