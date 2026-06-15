from app.services.ivr.ivr_models import IvrIntent, IvrState


LANGUAGE_DIGITS = {
    "1": "ta",
    "2": "kn",
    "3": "en",
}

STATE_DIGITS = {
    "1": IvrState.RECORD_QUERY,
    "2": IvrState.SCHEME_STATE,
    "3": IvrState.GRIEVANCE_RECORD,
    "4": IvrState.TRACK_GRIEVANCE,
    "5": IvrState.RECORD_QUERY,
}

SCHEME_STATE_DIGITS = {
    "1": "Tamil Nadu",
    "2": "Karnataka",
}

SCHEME_LAND_DIGITS = {
    "1": "owned",
    "2": "tenant",
    "3": "landless",
}


def menu_intent(digits: str | None) -> IvrIntent:
    if digits == "2":
        return IvrIntent.SCHEME_QUERY
    if digits == "3":
        return IvrIntent.GRIEVANCE_QUERY
    if digits == "4":
        return IvrIntent.GRIEVANCE_QUERY
    if digits == "5":
        return IvrIntent.CROP_RECOMMENDATION
    return IvrIntent.GENERAL_QUERY


def route_state_from_menu(digits: str | None) -> IvrState:
    return STATE_DIGITS.get(digits or "", IvrState.RECORD_QUERY)


def language_from_digits(digits: str | None) -> str:
    return LANGUAGE_DIGITS.get(digits or "", "ta")
