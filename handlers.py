import re
from io import BytesIO
from aiogram import Router, F, Bot
from aiogram.types import Message
from supabase import Client

from utils.logger import logger

router = Router()
BUCKET_NAME = "memes"

# Предлоги и союзы, которые не несут смысла при поиске
STOP_WORDS = {
    "и", "а", "но", "в", "во", "на", "с", "со", "к", "по", "у",
    "о", "об", "за", "из", "до", "от", "для", "не", "ни", "то", "же"
}


def extract_tags(text: str) -> list[str]:
    """Splits text caption into a list of unique normalized keyword tags."""
    if not text:
        return []
    # Вытаскиваем только буквы и цифры, приводя к нижнему регистру
    words = re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]+", text.lower())
    # Оставляем уникальные слова длиннее 1 символа, которых нет в стоп-словах
    return list({w for w in words if w not in STOP_WORDS and len(w) > 1})


@router.channel_post(F.photo)
async def handle_new_channel_photo(message: Message, bot: Bot, supabase: Client):
    """Automatically saves new channel photos with captions to Supabase storage and database."""
    caption = message.caption or ""
    # Игнорируем картинки без подписи, так как их невозможно найти по тексту
    if not caption.strip():
        logger.info(f"Skipped channel post #{message.message_id}: no caption")
        return

    logger.info(f"Received new channel post #{message.message_id} with caption: '{caption[:30]}...'")

    tags = extract_tags(caption)
    # Берем последний элемент списка — это фото в самом высоком разрешении
    best_photo = message.photo[-1]
    file_path = f"{message.message_id}.jpg"

    try:
        # Скачиваем картинку в оперативную память (без сохранения на диск)
        buffer = BytesIO()
        await bot.download(best_photo, destination=buffer)
        image_bytes = buffer.getvalue()

        # Загружаем файл в облачное хранилище Supabase Storage
        supabase.storage.from_(BUCKET_NAME).upload(
            path=file_path,
            file=image_bytes,
            file_options={"content-type": "image/jpeg", "upsert": "true"},
        )
        # Получаем прямую публичную ссылку на загруженную картинку
        public_url = supabase.storage.from_(BUCKET_NAME).get_public_url(file_path)

        # Записываем метаданные мема в таблицу базы данных
        data_payload = {
            "channel_message_id": message.message_id,
            "caption": caption,
            "tags": tags,
            "photo_url": public_url,
        }
        supabase.table("memes").upsert(
            data_payload,
            on_conflict="channel_message_id"
        ).execute()

        logger.info(f"Saved meme #{message.message_id} with tags: {tags[:5]}")
    except Exception as e:
        logger.error(f"Failed to save post #{message.message_id}: {e}")
