from app.config import settings


LANGUAGE_LABELS = {
    "ta": "Tamil",
    "kn": "Kannada",
    "en": "English",
}

LANGUAGE_DIGIT_LABELS = {
    "ta": "Press 1 for Tamil",
    "kn": "Press 2 for Kannada",
    "en": "Press 3 for English",
}

PROMPTS = {
    "menu": "Press 1 to ask a farming question. Press 2 for scheme eligibility. Press 3 to register a grievance. Press 4 to track a grievance. Press 5 for crop recommendations.",
    "record": "Ask your farming question after the beep.",
    "grievance": "Describe your grievance after the beep.",
    "tracking": "Enter the last five digits of your grievance tracking number.",
    "scheme_state": "For state, press 1 for Tamil Nadu. Press 2 for Karnataka.",
    "scheme_land": "For land ownership, press 1 if you own land. Press 2 if tenant or sharecropper. Press 3 if landless.",
    "scheme_income": "Enter annual income in rupees, then submit.",
}

LOCALIZED_PROMPTS = {
    "ta": {
        "menu": "விவசாய கேள்விக்கு 1 அழுத்தவும். திட்ட தகுதிக்கு 2 அழுத்தவும். புகார் பதிவு செய்ய 3 அழுத்தவும். புகார் நிலை அறிய 4 அழுத்தவும். பயிர் பரிந்துரைக்கு 5 அழுத்தவும்.",
        "record": "பீப் ஒலிக்குப் பிறகு உங்கள் விவசாய கேள்வியை கேளுங்கள்.",
        "grievance": "பீப் ஒலிக்குப் பிறகு உங்கள் புகாரை சொல்லுங்கள்.",
        "tracking": "உங்கள் புகார் எண்ணின் கடைசி ஐந்து இலக்கங்களை உள்ளிடவும்.",
        "scheme_state": "மாநிலத்திற்கு, தமிழ்நாடு என்றால் 1 அழுத்தவும். கர்நாடகா என்றால் 2 அழுத்தவும்.",
        "scheme_land": "நில உரிமைக்கு, சொந்த நிலம் என்றால் 1 அழுத்தவும். குத்தகை அல்லது பகிர்வு விவசாயி என்றால் 2 அழுத்தவும். நிலமில்லாதவர் என்றால் 3 அழுத்தவும்.",
        "scheme_income": "உங்கள் வருடாந்திர வருமானத்தை ரூபாயில் உள்ளிடவும்.",
    },
    "kn": {
        "menu": "ಕೃಷಿ ಪ್ರಶ್ನೆಗೆ 1 ಒತ್ತಿರಿ. ಯೋಜನೆ ಅರ್ಹತೆಗೆ 2 ಒತ್ತಿರಿ. ದೂರು ದಾಖಲಿಸಲು 3 ಒತ್ತಿರಿ. ದೂರು ಸ್ಥಿತಿ ತಿಳಿಯಲು 4 ಒತ್ತಿರಿ. ಬೆಳೆ ಶಿಫಾರಸಿಗೆ 5 ಒತ್ತಿರಿ.",
        "record": "ಬೀಪ್ ನಂತರ ನಿಮ್ಮ ಕೃಷಿ ಪ್ರಶ್ನೆಯನ್ನು ಕೇಳಿ.",
        "grievance": "ಬೀಪ್ ನಂತರ ನಿಮ್ಮ ದೂರನ್ನು ವಿವರಿಸಿ.",
        "tracking": "ನಿಮ್ಮ ದೂರು ಸಂಖ್ಯೆಯ ಕೊನೆಯ ಐದು ಅಂಕಿಗಳನ್ನು ನಮೂದಿಸಿ.",
        "scheme_state": "ರಾಜ್ಯಕ್ಕೆ, ತಮಿಳುನಾಡು ಎಂದರೆ 1 ಒತ್ತಿರಿ. ಕರ್ನಾಟಕ ಎಂದರೆ 2 ಒತ್ತಿರಿ.",
        "scheme_land": "ಭೂಸ್ವಾಮ್ಯಕ್ಕೆ, ಸ್ವಂತ ಭೂಮಿ ಎಂದರೆ 1 ಒತ್ತಿರಿ. ಬಾಡಿಗೆ ಅಥವಾ ಹಂಚಿಕೆ ರೈತ ಎಂದರೆ 2 ಒತ್ತಿರಿ. ಭೂಹೀನ ಎಂದರೆ 3 ಒತ್ತಿರಿ.",
        "scheme_income": "ನಿಮ್ಮ ವಾರ್ಷಿಕ ಆದಾಯವನ್ನು ರೂಪಾಯಿಯಲ್ಲಿ ನಮೂದಿಸಿ.",
    },
}


def enabled_languages() -> list[str]:
    languages = [language for language in settings.ivr_enabled_languages_list if language in LANGUAGE_LABELS]
    return languages or ["ta", "kn", "en"]


def default_language() -> str:
    language = settings.IVR_DEFAULT_LANGUAGE.strip().lower()
    return language if language in enabled_languages() else enabled_languages()[0]


def normalise_language(language: str | None) -> str:
    language = (language or "").strip().lower()
    return language if language in enabled_languages() else default_language()


def language_prompt() -> str:
    options = [LANGUAGE_DIGIT_LABELS[language] for language in enabled_languages()]
    return f"Welcome to {settings.IVR_AGENT_NAME}. {'. '.join(options)}."


def prompt_for(language: str | None, key: str) -> str:
    resolved_language = normalise_language(language)
    return LOCALIZED_PROMPTS.get(resolved_language, {}).get(key, PROMPTS[key])
