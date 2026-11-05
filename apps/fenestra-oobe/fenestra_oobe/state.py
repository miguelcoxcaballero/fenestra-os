"""Choices collected while going through the OOBE."""

from dataclasses import dataclass, field


@dataclass
class OobeState:
    ui_lang: str = "en"
    lang_locale: str = "en_US.UTF-8"
    country: str = "US"
    formats: str = "en_US.UTF-8"
    timezone: str = "UTC"
    layouts: list = field(default_factory=lambda: [("us", "")])
    hostname: str | None = None
    full_name: str = ""
    username: str = ""
    password: str = ""
    hint: str = ""
    online: bool = False
    uid: int | None = None
    privacy: dict = field(default_factory=dict)
    interests: list = field(default_factory=list)
    other_system_root: str | None = None
    import_requested: bool = False
    icon_choice: str = "default"
    icon_pack: str | None = None

    def forget_secrets(self):
        self.password = ""
