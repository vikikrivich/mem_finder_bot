import re
import nltk
from nltk.corpus import stopwords
from nltk.stem.snowball import SnowballStemmer
from supabase import Client

# Скачиваем словарь русских стоп-слов при первом запуске, если его еще нет
try:
    nltk.data.find("corpora/stopwords")
except LookupError:
    nltk.download("stopwords", quiet=True)

# Стеммер обрезает окончания слов (например, "котики" -> "котик") для умного поиска
stemmer = SnowballStemmer("russian")
STOP_WORDS = set(stopwords.words("russian")) - {"не", "нет"}
PUNCTUATION_REGEX = re.compile(r"[^\w\s]", re.UNICODE)


def stem_word(word: str) -> str:
    """Normalizes a word and extracts its root stem."""
    return stemmer.stem(word.strip().lower())


def extract_stems(text: str) -> list[str]:
    """Tokenizes text, removes stop words, and returns unique word stems."""
    clean_text = PUNCTUATION_REGEX.sub(" ", text.lower())
    stems = []
    for w in clean_text.split():
        if len(w) > 1 and w not in STOP_WORDS:
            stems.append(stem_word(w))
    # Убираем дубликаты, сохраняя исходный порядок слов
    return list(dict.fromkeys(stems))


def search_memes(supabase: Client, query: str) -> list[dict]:
    """Searches memes in Supabase using stemming and ranks results by relevance."""
    clean_query = PUNCTUATION_REGEX.sub(" ", query.lower()).strip()
    if not clean_query:
        return []

    query_stems = extract_stems(query)
    if not query_stems:
        return []

    # Формируем условия поиска для Supabase: совпадение фразы, корней в описании или тегах
    caption_filters = [f"caption.ilike.%{stem}%" for stem in query_stems]
    tags_filter = f"tags.ov.{{{','.join(query_stems)}}}"
    exact_phrase_filter = f"caption.ilike.%{clean_query}%"
    or_condition = ",".join([exact_phrase_filter] + caption_filters + [tags_filter])

    try:
        response = (
            supabase.table("memes")
            .select("id, photo_url, caption, tags")
            .not_.is_("photo_url", "null")
            .neq("photo_url", "")
            .or_(or_condition)
            .limit(200)
            .execute()
        )
        items = response.data or []
    except Exception:
        return []

    query_stems_set = set(query_stems)

    def calculate_score(item: dict) -> int:
        """Calculates a relevance score for sorting search results."""
        score = 0
        caption = (item.get("caption") or "").lower()
        meme_tag_stems = {stem_word(t) for t in (item.get("tags") or []) if t}

        # Бонус за точное вхождение всей фразы целиком
        if clean_query in caption:
            score += 100

        # Баллы за каждый найденный корень слова в описании
        matched_stems = sum(1 for stem in query_stems if stem in caption)
        score += matched_stems * 5

        # Бонус, если в описании нашлись вообще все слова из запроса
        if matched_stems == len(query_stems):
            score += 25

        # Баллы за совпадение с тегами мема
        score += len(query_stems_set.intersection(meme_tag_stems)) * 8
        return score

    # Сортируем найденные мемы от самых релевантных к менее подходящим
    items.sort(key=calculate_score, reverse=True)
    return items[:50]
