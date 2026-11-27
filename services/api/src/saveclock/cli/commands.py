"""The command table and its handlers: one HTTP call per step, mapped by operation id.

No rule lives here that the API owns (keyword shape, duration, vibe length): the CLI sends what
it was given and prints the API's answer. `COMMANDS` is the one owner of the command list; the
skill's command table is guarded against it (`make skill-check`).
"""

import urllib.parse
import webbrowser
from collections.abc import Callable, Iterator
from contextlib import ExitStack
from dataclasses import dataclass, field
from http import HTTPStatus
from pathlib import Path
from typing import Any

from saveclock.cli import files, schema, sse, waits
from saveclock.cli.client import ApiError, Client, CliError, NetworkError, Refused, valid_id
from saveclock.cli.output import emit, note

RENDER_STOP = {"ready", "failed", "canceled"}
UI_STOP = {"draft", "ready", "failed", "canceled"}  # where `status --watch` stops
UI_BAD = {"failed", "canceled"}
CHUNK = 1024 * 1024


@dataclass
class Ctx:
    client: Client
    as_json: bool
    app_origin: str


@dataclass(frozen=True)
class Command:
    name: str
    help: str
    handler: Callable[[Ctx, Any], int]
    args: list[tuple[tuple[str, ...], dict[str, Any]]] = field(default_factory=list)


def _wait_for(
    fetch: Callable[[], Any], done: Callable[[Any], bool], *, timeout: float, ident: str
) -> Any:  # noqa: ANN401
    """Poll until `done`; on timeout raise (exit 3) and cancel nothing: it is still running."""
    deadline = waits.now() + timeout
    while True:
        value = fetch()
        if done(value):
            return value
        if waits.now() >= deadline:
            raise NetworkError(
                f"still running: check with `saveclock status {ident}` (nothing was cancelled)",
                code="timeout",
            )
        waits.sleep(waits.POLL_S)


def _get(c: Ctx, op: str, **params: str) -> Any:  # noqa: ANN401
    return c.client.call(op, params=params).json()


def _chunks(path: Path) -> Iterator[bytes]:
    with path.open("rb") as fh:  # streamed: the song is never read into memory
        while chunk := fh.read(CHUNK):
            yield chunk


# --- new ---------------------------------------------------------------------------------
def cmd_new(c: Ctx, a: Any) -> int:  # noqa: ANN401
    song = Path(a.song)
    if not song.is_file():
        raise Refused(f"not a file: {song}")
    size = song.stat().st_size
    options: dict[str, Any] = {}
    if a.vibe is not None:
        options["vibe"] = a.vibe
    if a.keywords is not None:
        options["keywords_override"] = [w.strip() for w in a.keywords.split(",") if w.strip()]
    if a.duration is not None:
        options["duration"] = a.duration
    body: dict[str, Any] = {}
    if a.title is not None:
        body["title"] = a.title
    if options:
        body["options"] = options
    pid = c.client.call("create_project", json=body).json()["id"]
    headers = {
        "Content-Type": "application/octet-stream",
        "Content-Length": str(size),
        "X-Filename": urllib.parse.quote(song.name, safe=""),
    }
    try:
        up = c.client.call(
            "upload_song", params={"project_id": pid}, content=_chunks(song), headers=headers
        ).json()
    except CliError as err:  # the project exists: say so, the endpoint accepts a second upload
        err.details = {**err.details, "project_id": pid}
        raise
    out = schema.NewOut(project_id=pid, job_id=up["job_id"], ui_status=up["ui_status"])
    emit(out, f"project {pid}", as_json=c.as_json)
    return 0


# --- show --------------------------------------------------------------------------------
def cmd_show(c: Ctx, a: Any) -> int:  # noqa: ANN401
    pid = valid_id(a.project_id)
    p = _get(c, "get_project", project_id=pid)
    analysis = _get(c, "get_analysis", project_id=pid) if p["analysis"] else None
    plan = _get(c, "get_plan", project_id=pid) if p["plan"] else None
    song = p["song"]
    out = schema.ShowOut(
        project=schema.ShowProject(
            **{k: p[k] for k in ("id", "title", "ui_status", "status_reason", "flags", "options")}
        ),
        song=schema.ShowSong(
            **{k: song[k] for k in ("duration_s", "codec", "sample_rate", "channels")}
        )
        if song
        else None,
        analysis=schema.ShowAnalysis(
            tempo_bpm=analysis["tempo_bpm"],
            tempo_octave_adjust=analysis["tempo_octave_adjust"],
            confidence=schema.ShowConfidence(**analysis["confidence"]),
            fallback=analysis["fallback"],
            n_beats=len(analysis["beats_s"]),
            n_downbeats=len(analysis["downbeats_s"]),
            sections=[schema.ShowSection(**s) for s in analysis["sections"]],
            segment=schema.ShowSegment(**analysis["segment"]) if analysis["segment"] else None,
            low_confidence_ranges=analysis["low_confidence_ranges"],
        )
        if analysis
        else None,
        keywords=schema.ShowKeywords(
            source=plan["provenance"]["keyword_source"],
            override=p["options"].get("keywords_override"),
        )
        if plan
        else None,
        plan=schema.ShowPlan(
            version=plan["version"],
            frozen=plan["frozen"],
            total_frames=plan["total_frames"],
            n_cuts=len(plan["cuts"]),
        )
        if plan
        else None,
        render=schema.ShowRender(**p["render"]) if p["render"] else None,
    )
    emit(out, _show_text(out), as_json=c.as_json)
    return 0


def _show_text(o: schema.ShowOut) -> str:
    lines = [f"project {o.project.id}  {o.project.ui_status}"]
    if o.project.status_reason:
        lines.append(f"  reason: {o.project.status_reason}")
    if o.analysis:
        an = o.analysis
        lines.append(
            f"  tempo {an.tempo_bpm:g} bpm, confidence {an.confidence.band} "
            f"({an.confidence.score:.2f}), "
            f"{an.n_beats} beats"
        )
        lines += [f"  {s.id}: {s.start_s:g}-{s.end_s:g}s {s.label} {s.energy}" for s in an.sections]
    if o.project.options.get("vibe"):
        lines.append(f"  vibe: {o.project.options['vibe']}")
    if o.keywords:
        lines.append(f"  keywords: source {o.keywords.source}, override {o.keywords.override}")
    if o.plan:
        lines.append(
            f"  plan v{o.plan.version}: {o.plan.n_cuts} cuts, {o.plan.total_frames} frames"
        )
    if o.render:
        lines.append(f"  render {o.render.id}: {o.render.state}")
    return "\n".join(lines)


# --- keywords ----------------------------------------------------------------------------
def cmd_keywords(c: Ctx, a: Any) -> int:  # noqa: ANN401
    pid = valid_id(a.project_id)
    base = _get(c, "get_plan", project_id=pid)["version"]
    ops = [{"op": "set_keywords", "keywords": list(a.words)}]
    try:
        resp = _patch(c, pid, base, ops)
    except ApiError as err:
        if err.code != "plan_version_conflict":
            raise
        base = _get(c, "get_plan", project_id=pid)["version"]  # once: the plan moved under us
        resp = _patch(c, pid, base, ops)
    if resp.status_code != HTTPStatus.ACCEPTED:  # a plan came back at once: nothing to wait for
        plan = resp.json()
        out = schema.KeywordsOut(
            project_id=pid, job_id=None, applied=True,
            plan_version=plan["version"], keyword_source=plan["provenance"]["keyword_source"],
        )  # fmt: skip
        emit(out, f"keywords set, plan v{plan['version']}", as_json=c.as_json)
        return 0
    job = resp.json()["job_id"]
    if a.no_wait:
        out = schema.KeywordsOut(
            project_id=pid, job_id=job, applied=None, plan_version=None, keyword_source=None
        )
        emit(out, f"replan started (job {job})", as_json=c.as_json)
        return 0
    timeout = a.timeout if a.timeout is not None else waits.WAIT_REPLAN_S
    p = _wait_for(
        lambda: _get(c, "get_project", project_id=pid),
        lambda p: p["ui_status"] in UI_STOP,
        timeout=timeout,
        ident=pid,
    )
    plan = p["plan"]
    # A replan replaces an unfrozen plan in place (same version), so the version cannot tell
    # success from failure; a replan that ends without a plan always leaves a `status_reason`
    # (P9-4, corrected against the code) and puts the previous plan back.
    if p["ui_status"] == "draft" and plan and not p["status_reason"]:
        out = schema.KeywordsOut(
            project_id=pid, job_id=job, applied=True,
            plan_version=plan["version"], keyword_source=plan["keyword_source"],
        )  # fmt: skip
        emit(
            out,
            f"keywords applied: plan v{plan['version']}, source {plan['keyword_source']}",
            as_json=c.as_json,
        )
        return 0
    # a failed replan returns the project to draft with the previous plan (P9-4)
    raise CliError(
        "keywords_not_applied",
        "keywords not applied, previous plan kept"
        + (f" ({p['status_reason']})" if p["status_reason"] else ""),
        details={"ui_status": p["ui_status"], "status_reason": p["status_reason"]},
    )


def _patch(c: Ctx, pid: str, base: int, ops: list[dict[str, Any]]) -> Any:  # noqa: ANN401
    return c.client.call(
        "patch_plan", params={"project_id": pid}, json={"base_version": base, "ops": ops}
    )


# --- plan --------------------------------------------------------------------------------
def cmd_plan(c: Ctx, a: Any) -> int:  # noqa: ANN401
    pid = valid_id(a.project_id)
    p = _get(c, "get_plan", project_id=pid)
    cuts = [
        schema.PlanCut(
            index=x["index"],
            out_start_frame=x["out_start_frame"],
            out_end_frame=x["out_end_frame"],
            section=x["section"]["id"],
            clip_provider=x["clip"]["provider"],
            clip_id=x["clip"]["provider_id"],
            keywords=x["clip"]["keywords"],
            locked=x["clip"]["locked"],
        )
        for x in p["cuts"]
    ]
    out = schema.PlanCliOut(
        project_id=pid, version=p["version"], frozen=p["frozen"], total_frames=p["total_frames"],
        keyword_source=p["provenance"]["keyword_source"], cuts=cuts,
    )  # fmt: skip
    rows = [f"plan v{out.version} ({out.keyword_source}), {out.total_frames} frames"]
    rows.append("  cut  frames          section  clip                      locked")
    rows += [
        f"  {x.index:>3}  {x.out_start_frame:>5}-{x.out_end_frame:<7} {x.section:<8} "
        f"{x.clip_provider}:{x.clip_id:<18} {'yes' if x.locked else 'no'}"
        for x in cuts
    ]
    emit(out, "\n".join(rows), as_json=c.as_json)
    return 0


# --- render ------------------------------------------------------------------------------
def cmd_render(c: Ctx, a: Any) -> int:  # noqa: ANN401
    pid = valid_id(a.project_id)
    body = {"plan_version": a.plan_version} if a.plan_version is not None else None
    rid = c.client.call("create_render", params={"project_id": pid}, json=body).json()["render_id"]
    if a.no_wait:
        out = schema.RenderCliOut(
            project_id=pid,
            render_id=rid,
            plan_version=None,
            state=None,
            error_code=None,
            verify=None,
        )
        emit(out, f"render {rid} started", as_json=c.as_json)
        return 0
    timeout = a.timeout if a.timeout is not None else waits.WAIT_RENDER_S
    r = _wait_for(
        lambda: _get(c, "get_render", render_id=rid),
        lambda r: r["state"] in RENDER_STOP,
        timeout=timeout,
        ident=pid,
    )
    v = r["verify"]
    verify = (
        schema.VerifyLine(
            passed=v["passed"],
            blocks=v["blocks"],
            warns=v["warns"],
            failed_checks=[f["id"] for f in v["failed"]],
            render_ms=v["render_ms"],
            verify_ms=v["verify_ms"],
        )
        if v
        else None
    )
    out = schema.RenderCliOut(
        project_id=pid, render_id=rid, plan_version=r["plan_version"], state=r["state"],
        error_code=r["error_code"], verify=verify,
    )  # fmt: skip
    if r["state"] != "ready":
        emit(out, f"render {rid} {r['state']}: {r['error_code']}", as_json=c.as_json)
        return 1
    line = f"render {rid} ready"
    if verify:
        state = "passed" if verify.passed else "FAILED"
        line += f" (verify {state}: {verify.blocks} blocks, {verify.warns} warns)"
    emit(out, line, as_json=c.as_json)
    return 0


# --- export ------------------------------------------------------------------------------
def _download(
    c: Ctx, rid: str, kinds: tuple[str, ...], directory: Path, *, force: bool
) -> list[schema.ExportFile]:
    """Open every download first (headers only): a name clash refuses before any file is written."""
    with ExitStack() as stack:
        opened = [
            (k, stack.enter_context(
                c.client.stream("download_render", params={"render_id": rid}, query={"kind": k})
            ))
            for k in kinds
        ]  # fmt: skip
        names = [
            files.safe_name(r.headers.get("content-disposition"), f"{rid}-{k}.{files.KIND_EXT[k]}")
            for k, r in opened
        ]
        clash = [directory / n for n in names if (directory / n).exists()]
        if clash and not force:
            raise Refused(f"{clash[0]} exists; use --force to overwrite")
        out = []
        for (kind, r), name in zip(opened, names, strict=True):
            try:
                path = files.write_stream(r.iter_bytes(CHUNK), directory, name, force=force)
            except FileExistsError as exc:
                raise Refused(f"{exc} exists; use --force to overwrite") from exc
            out.append(schema.ExportFile(kind=kind, path=str(path)))
        return out


def cmd_export(c: Ctx, a: Any) -> int:  # noqa: ANN401
    pid = valid_id(a.project_id)
    try:
        directory = files.target_dir(a.out)
    except NotADirectoryError as exc:
        raise Refused(str(exc)) from exc
    render = _get(c, "get_project", project_id=pid)["render"]
    if not render or render["state"] != "ready":
        raise CliError(
            "conflict", f"no ready render for {pid}: run `saveclock render {pid}` first",
            details={"reason": "not_ready"},
        )  # fmt: skip
    rid = render["id"]
    got: list[schema.ExportFile] = []
    credits_text = None
    if a.mode == "a":
        c.client.call("request_mode_a", params={"render_id": rid})
        timeout = a.timeout if a.timeout is not None else waits.WAIT_MODE_A_S
        r = _wait_for(
            lambda: _get(c, "get_render", render_id=rid),
            lambda r: r["mode_a_state"] in {"ready", "failed"},
            timeout=timeout,
            ident=pid,
        )
        if r["mode_a_state"] != "ready":
            raise CliError("mode_a_failed", f"the Mode A remux failed for render {rid}")
        got += _download(c, rid, ("with_song",), directory, force=a.force)
    else:
        kinds = ("silent_video", "cutlist_json", "cutlist_csv")
        got += _download(c, rid, kinds, directory, force=a.force)
        credits_text = _get(c, "get_credits", project_id=pid)["text"]
    out = schema.ExportOut(mode=a.mode, render_id=rid, files=got, credits_text=credits_text)
    text = "\n".join(f"{f.kind}: {f.path}" for f in got)
    if credits_text:
        text += f"\n\ncredits:\n{credits_text}"
    emit(out, text, as_json=c.as_json)
    return 0


# --- status ------------------------------------------------------------------------------
def _status_project(p: dict[str, Any]) -> schema.StatusProject:
    plan, render = p.get("plan"), p.get("render")
    return schema.StatusProject(
        id=p["id"], title=p["title"], ui_status=p["ui_status"], status_reason=p["status_reason"],
        plan_version=plan["version"] if plan else None,
        render_id=render["id"] if render else None,
        render_state=render["state"] if render else None,
        mode_a_state=render["mode_a_state"] if render else None,
    )  # fmt: skip


def _status_text(s: schema.StatusProject) -> str:
    lines = [f"project {s.id}  {s.ui_status}" + (f"  ({s.title})" if s.title else "")]
    if s.status_reason:
        lines.append(f"  reason: {s.status_reason}")
    if s.plan_version:
        lines.append(f"  plan v{s.plan_version}")
    if s.render_id:
        lines.append(f"  render {s.render_id}: {s.render_state}, mode a: {s.mode_a_state or '-'}")
    return "\n".join(lines)


def _handle_event(c: Ctx, ev: sse.Event) -> int | None:
    """An exit code when the event ends the watch, else None."""
    data = ev.data if isinstance(ev.data, dict) else {}
    if ev.name == "state":
        ui = data.get("ui_status")
        note(f"state: {ui}", as_json=c.as_json)
        if ui in UI_BAD:
            return 1
        return 0 if ui in UI_STOP else None
    if ev.name == "progress":
        note(f"{data.get('step')}: {data.get('pct')}% {data.get('message_key')}", as_json=c.as_json)
    elif ev.name in {"draft_ready", "render_ready", "mode_a_ready"}:
        note(ev.name, as_json=c.as_json)
        return 0
    elif ev.name == "failed":
        note(f"failed: {data.get('stage')} {data.get('code')}", as_json=c.as_json)
        return 1
    return None


def _watch(c: Ctx, pid: str, timeout: float) -> int:
    deadline = waits.now() + timeout
    while True:
        try:
            with c.client.stream("stream_events", params={"project_id": pid}) as resp:
                for ev in sse.parse(resp.iter_lines()):
                    done = _handle_event(c, ev)
                    if done is not None:
                        return done
                    if waits.now() >= deadline:
                        break
        except ApiError as err:
            if err.code == "conflict" and err.details.get("reason") == "too_many_streams":
                return _poll_status(c, pid, deadline)
            raise
        if waits.now() >= deadline:
            raise NetworkError(
                f"still running: check with `saveclock status {pid}` (nothing was cancelled)",
                code="timeout",
            )
        waits.sleep(waits.POLL_S)  # the server ended the stream: reconnect (a fresh snapshot)


def _poll_status(c: Ctx, pid: str, deadline: float) -> int:
    p = _wait_for(
        lambda: _get(c, "get_project", project_id=pid),
        lambda p: p["ui_status"] in UI_STOP,
        timeout=max(deadline - waits.now(), 0.0),
        ident=pid,
    )
    return 1 if p["ui_status"] in UI_BAD else 0


def cmd_status(c: Ctx, a: Any) -> int:  # noqa: ANN401
    if a.project_id is None:
        items = c.client.call("list_projects").json()["items"]
        lines = [
            schema.StatusLine(id=i["id"], ui_status=i["ui_status"], title=i["title"]) for i in items
        ]
        text = (
            "\n".join(f"{x.id}  {x.ui_status:<10} {x.title or ''}" for x in lines) or "no projects"
        )
        emit(schema.StatusOut(project=None, projects=lines), text, as_json=c.as_json)
        return 0
    pid = valid_id(a.project_id)
    code = 0
    if a.watch:
        timeout = a.timeout if a.timeout is not None else waits.WAIT_WATCH_S
        code = _watch(c, pid, timeout)
    st = _status_project(_get(c, "get_project", project_id=pid))
    emit(schema.StatusOut(project=st, projects=None), _status_text(st), as_json=c.as_json)
    return 1 if code or st.ui_status in UI_BAD else 0


# --- open --------------------------------------------------------------------------------
def cmd_open(c: Ctx, a: Any) -> int:  # noqa: ANN401
    url = f"{c.app_origin.rstrip('/')}/projects/{valid_id(a.project_id)}"
    opened = webbrowser.open(url)
    emit(schema.OpenOut(url=url, opened=bool(opened)), url, as_json=c.as_json)
    return 0


_TIMEOUT = (
    ("--timeout",),
    {
        "type": float,
        "metavar": "SECONDS",
        "help": "give up waiting after this long (the job keeps running)",
    },
)
_NO_WAIT = (
    ("--no-wait",),
    {"action": "store_true", "help": "return as soon as the request is accepted"},
)

COMMANDS: list[Command] = [
    Command("new", "create a project and upload a song", cmd_new, [
        (("song",), {"help": "path of the song file"}),
        (("--title",), {"help": "project title"}),
        (("--vibe",), {"help": "a short mood phrase the keywords are chosen from"}),
        (("--keywords",), {"help": "comma-separated keywords to use instead of generated ones"}),
        (("--duration",), {"type": int, "help": "video length in seconds (the API validates it)"}),
    ]),
    Command("show", "print the analysis summary and plan summary of a project", cmd_show, [
        (("project_id",), {"help": "project id"}),
    ]),
    Command("keywords", "set the stock-footage keywords (replans the draft)", cmd_keywords, [
        (("action",), {"choices": ["set"], "help": "only `set`"}),
        (("project_id",), {"help": "project id"}),
        (("words",), {"nargs": "+", "help": "one or more keywords"}),
        _NO_WAIT, _TIMEOUT,
    ]),
    Command("plan", "print the cuts of the current plan", cmd_plan, [
        (("project_id",), {"help": "project id"}),
    ]),
    Command("render", "render the video and wait until it is ready", cmd_render, [
        (("project_id",), {"help": "project id"}),
        (("--plan-version",), {"type": int, "help": "render this plan version (default: latest)"}),
        _NO_WAIT, _TIMEOUT,
    ]),
    Command("export", "download a finished render", cmd_export, [
        (("project_id",), {"help": "project id"}),
        (("--mode",), {
            "choices": ["a", "b"], "required": True,
            "help": "a: video with the song; b: silent video, cut list and credits",
        }),
        (("--out",), {"help": "output directory (default: the current directory)"}),
        (("--force",), {"action": "store_true", "help": "overwrite existing files"}),
        _TIMEOUT,
    ]),
    Command("status", "show one project, follow it, or list all projects", cmd_status, [
        (("project_id",), {"nargs": "?", "help": "project id (omit to list every project)"}),
        (("--watch",), {"action": "store_true", "help": "follow the project until it settles"}),
        _TIMEOUT,
    ]),
    Command("open", "open the project in the browser", cmd_open, [
        (("project_id",), {"help": "project id"}),
    ]),
]  # fmt: skip

__all__ = ["COMMANDS", "Command", "Ctx"]
