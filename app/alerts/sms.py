from app.config import settings


class SmsProvider:
    def send(self, to: str, message: str):
        raise NotImplementedError


class ConsoleSms(SmsProvider):
    def send(self, to: str, message: str):
        print(f"[SMS to {to}] {message}")


class TwilioSms(SmsProvider):
    def __init__(self):
        from twilio.rest import Client
        self.client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

    def send(self, to: str, message: str):
        self.client.messages.create(
            body=message,
            from_=settings.twilio_from_number,
            to=to,
        )


def get_sms_provider() -> SmsProvider:
    if settings.sms_provider == "twilio":
        return TwilioSms()
    return ConsoleSms()
