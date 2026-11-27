"""The footage credits of a plan (endpoint #16): the attribution list and one ready-to-copy text."""

from dataclasses import dataclass

from saveclock.domain.edit_plan import EditPlan

PROVIDER_NAMES = {"pexels": "Pexels", "pixabay": "Pixabay"}


@dataclass(frozen=True)
class CreditItem:
    provider: str
    author: str | None
    page_url: str
    uses: int


@dataclass(frozen=True)
class Credits:
    items: list[CreditItem]
    text: str


def _line(item: CreditItem) -> str:
    name = PROVIDER_NAMES.get(item.provider, item.provider.title())
    if item.author:
        return f"Footage: {item.author} on {name} - {item.page_url}"
    return f"Footage on {name} - {item.page_url}"


def credits(plan: EditPlan) -> Credits:
    """Deduplicated by (provider, author, page_url), first use first; `None` is an author value."""
    counts: dict[tuple[str, str | None, str], int] = {}
    for cut in plan.cuts:
        a = cut.clip.attribution
        key = (cut.clip.provider, a.author, a.page_url)
        counts[key] = counts.get(key, 0) + 1
    items = [CreditItem(p, author, url, n) for (p, author, url), n in counts.items()]
    return Credits(items, "\n".join(_line(i) for i in items))
