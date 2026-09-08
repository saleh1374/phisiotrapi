"""Translation + categorization services for the auto news reader."""
import os

from .models import NewsFeed

CATEGORY_KEYWORDS = {
    NewsFeed.Category.TECH: ["technology", "device", "robot", "app", "digital", "wearable", "تکنولوژی", "دستگاه"],
    NewsFeed.Category.CONFERENCE: ["conference", "congress", "symposium", "workshop", "همایش", "کنگره"],
    NewsFeed.Category.METHODS: ["new method", "protocol", "technique", "innovation", "approach", "متد", "روش"],
    # Everything else falls into clinical research.
}

TRANSLATION_KEYWORDS = {
    "back pain": "کمردرد",
    "knee": "زانو",
    "neck": "گردن",
    "shoulder": "شانه",
    "rehabilitation": "توانبخشی",
    "physiotherapy": "فیزیوتراپی",
    "physical therapy": "فیزیوتراپی",
    "exercise": "تمرین",
    "stroke": "سکته مغزی",
    "pain": "درد",
    "patients": "بیماران",
    "study": "مطالعه",
    "research": "پژوهش",
    "treatment": "درمان",
    "therapy": "درمان",
    "improves": "بهبود می‌بخشد",
    "reduces": "کاهش می‌دهد",
    "walking": "راه رفتن",
    "balance": "تعادل",
    "muscle": "عضله",
    "joint": "مفصل",
    "chronic": "مزمن",
    "new": "جدید",
    "shows": "نشان می‌دهد",
    "found": "یافت شد",
    "effective": "موثر",
    "significantly": "به‌طور قابل توجهی",
    "women": "زنان",
    "older adults": "سالمندان",
    "program": "برنامه",
    "results": "نتایج",
}


def categorize(text: str) -> str:
    """Classify an article into a news category based on keywords."""
    lowered = (text or "").lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            return category
    return NewsFeed.Category.CLINICAL


def translate_text(text: str) -> str:
    """Translate a short text (title/summary) to fluent Persian.

    Pluggable backends:
      - If GOOGLE_TRANSLATE_API_KEY is set, calls the Google Cloud Translation API.
      - If GEMINI_API_KEY is set, calls the Gemini API.
      - Otherwise falls back to a keyword-based dictionary translation
        (deterministic, no external dependency — perfect for development).
    """
    google_key = os.getenv("GOOGLE_TRANSLATE_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY")

    if google_key:
        try:
            return _translate_google(text, google_key)
        except Exception:
            pass
    if gemini_key:
        try:
            return _translate_gemini(text, gemini_key)
        except Exception:
            pass
    return _translate_dictionary(text)


def _translate_google(text: str, api_key: str) -> str:
    import requests

    resp = requests.post(
        "https://translation.googleapis.com/language/translate/v2",
        params={"key": api_key},
        json={"q": text, "target": "fa", "format": "text"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["data"]["translations"][0]["translatedText"]


def _translate_gemini(text: str, api_key: str) -> str:
    import requests

    resp = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent",
        params={"key": api_key},
        json={
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "Translate the following English medical/physiotherapy text into "
                                "fluent, natural Persian (Farsi). Keep medical terms accurate. "
                                f"Only output the translation:\n\n{text}"
                            )
                        }
                    ]
                }
            ]
        },
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


def _translate_dictionary(text: str) -> str:
    """Deterministic keyword-based translation used when no API key exists."""
    lowered = (text or "").lower()
    result = text
    for en, fa in sorted(TRANSLATION_KEYWORDS.items(), key=lambda kv: -len(kv[0])):
        if en in lowered:
            result = result.replace(en, fa).replace(en.capitalize(), fa)
    return result


def enrich_article(entry: dict) -> dict:
    """Turn a raw RSS entry into a NewsFeed-ready payload."""
    title_en = entry.get("title", "").strip()
    summary_en = entry.get("summary", entry.get("description", "")).strip()

    title_fa = translate_text(title_en)
    summary_fa = translate_text(summary_en[:500])

    image_url = ""
    media = entry.get("media_content") or entry.get("media_thumbnail")
    if media and media[0].get("url"):
        image_url = media[0]["url"]

    from .models import NewsFeed

    return {
        "source_url": entry.get("link", "").strip(),
        "title_fa": title_fa or title_en,
        "title_en": title_en,
        "summary_fa": summary_fa,
        "image_url": image_url,
        "category": categorize(f"{title_en} {summary_en}"),
    }