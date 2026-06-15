from app.services.ivr.telephony_provider import BaseTelephonyProvider


class MockTelephonyProvider(BaseTelephonyProvider):
    name = "mock"

    def say(self, prompt: str, audio_url: str | None = None) -> dict:
        return {"provider": self.name, "action": "say", "prompt": prompt, "audio_url": audio_url}

    def collect_digits(self, prompt: str, max_digits: int = 1, audio_url: str | None = None) -> dict:
        return {
            "provider": self.name,
            "action": "collect_digits",
            "prompt": prompt,
            "audio_url": audio_url,
            "max_digits": max_digits,
        }

    def record(self, prompt: str, audio_url: str | None = None) -> dict:
        return {"provider": self.name, "action": "record", "prompt": prompt, "audio_url": audio_url}

    def hangup(self, prompt: str, audio_url: str | None = None) -> dict:
        return {"provider": self.name, "action": "hangup", "prompt": prompt, "audio_url": audio_url}
