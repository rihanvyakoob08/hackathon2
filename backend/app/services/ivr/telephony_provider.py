from abc import ABC, abstractmethod

from app.services.ivr.ivr_models import IvrAction


class BaseTelephonyProvider(ABC):
    name = "base"

    @abstractmethod
    def say(self, prompt: str, audio_url: str | None = None) -> dict:
        raise NotImplementedError

    @abstractmethod
    def collect_digits(self, prompt: str, max_digits: int = 1, audio_url: str | None = None) -> dict:
        raise NotImplementedError

    @abstractmethod
    def record(self, prompt: str, audio_url: str | None = None) -> dict:
        raise NotImplementedError

    @abstractmethod
    def hangup(self, prompt: str, audio_url: str | None = None) -> dict:
        raise NotImplementedError

    def render(self, action: IvrAction) -> dict:
        if action.record:
            return self.record(action.prompt, action.audio_url)
        if action.collect_digits:
            return self.collect_digits(action.prompt, action.max_digits, action.audio_url)
        if action.type == "hangup":
            return self.hangup(action.prompt, action.audio_url)
        return self.say(action.prompt, action.audio_url)
