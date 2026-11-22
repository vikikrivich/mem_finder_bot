import random
from supabase import Client
from utils.logger import logger


def get_random_meme(supabase: Client) -> dict | None:
    """Retrieves a single random meme record from the Supabase database."""
    try:
        # Узнаем общее количество записей в таблице
        count_response = (
            supabase.table("memes")
            .select("id", count="exact")
            .limit(1)
            .execute()
        )
        total_count = count_response.count or 0
        if total_count == 0:
            return None

        # Выбираем случайный порядковый номер и запрашиваем только одну эту строку
        random_index = random.randint(0, total_count - 1)
        response = (
            supabase.table("memes")
            .select("id, photo_url")
            .not_.is_("photo_url", "null")
            .range(random_index, random_index)
            .execute()
        )

        return response.data[0] if response.data else None

    except Exception as e:
        logger.error(f"Error fetching random meme: {e}")
        return None
