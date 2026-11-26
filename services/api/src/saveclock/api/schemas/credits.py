from pydantic import BaseModel, ConfigDict

from saveclock.domain.credits import Credits


class CreditItemOut(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: str
    author: str | None
    page_url: str
    uses: int


class CreditsOut(BaseModel):
    """The footage attributions of the working plan and one ready-to-copy credits text."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[CreditItemOut]
    text: str

    @classmethod
    def of(cls, c: Credits) -> "CreditsOut":
        return cls(
            items=[
                CreditItemOut(
                    provider=i.provider, author=i.author, page_url=i.page_url, uses=i.uses
                )
                for i in c.items
            ],
            text=c.text,
        )
