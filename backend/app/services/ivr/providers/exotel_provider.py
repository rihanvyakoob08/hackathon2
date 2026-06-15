from app.services.ivr.providers.mock_provider import MockTelephonyProvider


class ExotelProvider(MockTelephonyProvider):
    name = "exotel"
