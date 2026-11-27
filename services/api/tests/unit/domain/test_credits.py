from saveclock.domain import edit_plan as ep
from saveclock.domain.credits import credits
from tests.unit.domain.plan_support import plan


def attributed(p: ep.EditPlan, authors: list[str | None], pages: list[str]) -> ep.EditPlan:
    cuts = [
        c.model_copy(
            update={
                "clip": c.clip.model_copy(
                    update={
                        "attribution": ep.Attribution(
                            author=authors[i % len(authors)],
                            author_url=None,
                            page_url=pages[i % len(pages)],
                        )
                    }
                )
            }
        )
        for i, c in enumerate(p.cuts)
    ]
    return p.model_copy(update={"cuts": cuts})


def test_items_are_deduplicated_in_first_use_order_with_counts() -> None:
    p = attributed(
        plan(128.0, "e3", seconds=15).plan, ["Ann", "Bob"], ["https://p/a", "https://p/b"]
    )
    result = credits(p)
    assert [(i.author, i.page_url) for i in result.items] == [
        ("Ann", "https://p/a"),
        ("Bob", "https://p/b"),
    ]
    assert sum(i.uses for i in result.items) == len(p.cuts)
    assert result.text.splitlines() == [
        "Footage: Ann on Pexels - https://p/a",
        "Footage: Bob on Pexels - https://p/b",
    ]


def test_a_null_author_line_has_no_author_and_no_none() -> None:
    p = attributed(plan(128.0, "e3", seconds=15).plan, [None, "Ann"], ["https://p/x"])
    result = credits(p)
    assert result.text.splitlines()[0] == "Footage on Pexels - https://p/x"
    assert "None" not in result.text
    # a null author and a named one on the same page are two items
    assert [i.author for i in result.items] == [None, "Ann"]


def test_an_unknown_provider_is_named_by_its_title() -> None:
    p = plan(128.0, "e3", seconds=15).plan
    cuts = [
        c.model_copy(update={"clip": c.clip.model_copy(update={"provider": "pixabay"})})
        for c in p.cuts
    ]
    assert credits(p.model_copy(update={"cuts": cuts})).text.startswith("Footage: A on Pixabay")
    cuts = [
        c.model_copy(update={"clip": c.clip.model_copy(update={"provider": "vimeo"})})
        for c in p.cuts
    ]
    assert "on Vimeo" in credits(p.model_copy(update={"cuts": cuts})).text


def test_a_plan_with_no_cuts_gives_an_empty_credit() -> None:
    p = plan(128.0, "e3", seconds=15).plan.model_copy(update={"cuts": []})
    result = credits(p)
    assert (result.items, result.text) == ([], "")
