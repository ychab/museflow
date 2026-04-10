import asyncio
import dataclasses
import tempfile
from contextlib import AsyncExitStack
from enum import StrEnum
from pathlib import Path

from pydantic import EmailStr
from pydantic import TypeAdapter

import typer
from rich.pretty import Pretty

from museflow.domain.entities.taste import TasteProfile
from museflow.domain.exceptions import TasteProfileNotFoundException
from museflow.domain.exceptions import UserNotFound
from museflow.infrastructure.entrypoints.cli.commands.taste import app
from museflow.infrastructure.entrypoints.cli.commands.taste import console
from museflow.infrastructure.entrypoints.cli.dependencies import get_db
from museflow.infrastructure.entrypoints.cli.dependencies import get_taste_profile_repository
from museflow.infrastructure.entrypoints.cli.dependencies import get_user_repository
from museflow.infrastructure.entrypoints.cli.parsers import parse_email


class ViewFormat(StrEnum):
    json = "json"
    python = "python"
    html = "html"


@app.command("view", help="View a taste profile.")
def view(
    email: str = typer.Option(..., help="User email address", parser=parse_email),
    name: str = typer.Option(..., help="Profile name (unique per user)"),
    output_format: ViewFormat = typer.Option(
        ViewFormat.json, "--format", help="Output format: json, python, or html (browser)"
    ),
) -> None:
    try:
        taste_profile = asyncio.run(view_logic(email=email, name=name))
    except UserNotFound as e:
        raise typer.BadParameter(f"User not found with email: {email}") from e
    except TasteProfileNotFoundException as e:
        raise typer.BadParameter(f"Taste profile not found with name: {name}") from e
    except Exception as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e

    if output_format == ViewFormat.json:
        json_bytes = TypeAdapter(TasteProfile).dump_json(taste_profile, indent=2)
        console.print_json(json_bytes.decode())
    elif output_format == ViewFormat.python:
        console.print(Pretty(dataclasses.asdict(taste_profile)))
    else:  # html
        html = generate_profile_html_content(taste_profile)
        filepath = generate_profile_html_file(html)
        file_uri = filepath.absolute().as_uri()
        typer.echo(f"Opening browser to show the taste profile: {file_uri}")
        typer.launch(file_uri)


async def view_logic(email: EmailStr, name: str) -> TasteProfile:
    async with AsyncExitStack() as stack:
        session = await stack.enter_async_context(get_db())

        user_repository = get_user_repository(session)
        taste_profile_repository = get_taste_profile_repository(session)

        user = await user_repository.get_by_email(email)
        if user is None:
            raise UserNotFound()

        taste_profile = await taste_profile_repository.get(user_id=user.id, name=name)
        if not taste_profile:
            raise TasteProfileNotFoundException()

        return taste_profile


def generate_profile_html_content(taste_profile: TasteProfile) -> str:
    # fmt: off
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>MuseFlow | {taste_profile.name}</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;700;800&display=swap');
            body {{ font-family: 'Plus Jakarta Sans', sans-serif; background-color: #020617; color: #f1f5f9; }}
            .glass-card {{ background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(51, 65, 85, 0.5); backdrop-filter: blur(8px); }}
            .timeline-dot {{ position: relative; }}
            .timeline-dot::before {{ content: ''; position: absolute; left: -25px; top: 8px; width: 10px; height: 10px; background: #38bdf8; border-radius: 50%; box-shadow: 0 0 10px #38bdf8; }}
        </style>
    </head>
    <body class="p-6 md:p-12 leading-relaxed">
        <div class="max-w-5xl mx-auto space-y-10">

            <header class="flex flex-col md:flex-row justify-between items-start border-b border-slate-800 pb-8 gap-6">
                <div>
                    <span class="text-sky-400 font-bold tracking-widest text-xs uppercase">Personality Archetype</span>
                    <h1 class="text-5xl font-extrabold tracking-tight mt-1">{taste_profile.profile['personality_archetype']}</h1>
                    <div class="flex gap-4 mt-4 text-slate-500 text-xs font-mono">
                        <span>ID: {taste_profile.id}</span>
                        <span>USER: {taste_profile.user_id}</span>
                    </div>
                </div>
                <div class="glass-card p-6 rounded-3xl text-center min-w-[160px]">
                    <div class="text-4xl font-black text-white">{f"{taste_profile.tracks_count:,}"}</div>
                    <div class="text-[10px] uppercase tracking-widest text-slate-500 mt-1">Total Tracks</div>
                </div>
            </header>

            <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
                <section class="lg:col-span-2 space-y-6">
                    <div class="glass-card p-8 rounded-[2rem]">
                        <h2 class="text-sky-400 font-bold uppercase text-[10px] tracking-widest mb-4">The Narrative</h2>
                        <p class="text-xl font-light text-slate-200 italic leading-relaxed">"{taste_profile.profile['musical_identity_summary']}"</p>
                    </div>

                    <div class="glass-card p-8 rounded-[2rem] space-y-4">
                        <h2 class="text-purple-400 font-bold uppercase text-[10px] tracking-widest mb-2">Life Phase Insights</h2>
                        {"".join(f'<div class="flex gap-4 text-sm"><span class="text-slate-500">•</span><span class="text-slate-300">{insight}</span></div>' for insight in taste_profile.profile.get('life_phase_insights', []))}
                    </div>
                </section>

                <aside class="space-y-6">
                    <div class="glass-card p-6 rounded-[2rem]">
                        <h2 class="text-emerald-400 font-bold uppercase text-[10px] tracking-widest mb-4">Behavioral Traits</h2>
                        {"".join(f'''
                            <div class="mb-4">
                                <div class="flex justify-between text-xs mb-1"><span>{k.replace("_", " ").title()}</span><span>{int(v * 100)}%</span></div>
                                <div class="w-full bg-slate-800 h-1.5 rounded-full"><div class="bg-emerald-500 h-1.5 rounded-full" style="width: {v * 100}%"></div></div>
                            </div>
                        ''' for k, v in taste_profile.profile['behavioral_traits'].items())}
                    </div>

                    <div class="glass-card p-6 rounded-[2rem] border-t-2 border-sky-500">
                        <h2 class="text-sky-400 font-bold uppercase text-[10px] tracking-widest mb-2">Discovery Style</h2>
                        <div class="text-lg font-bold">{taste_profile.profile.get('discovery_style', 'Unknown')}</div>
                    </div>
                </aside>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div class="glass-card p-8 rounded-[2rem]">
                    <h2 class="text-pink-500 font-bold uppercase text-[10px] tracking-widest mb-6">Core Identity DNA</h2>
                    <div class="grid grid-cols-2 gap-4">
                        {"".join(f'<div class="bg-slate-900/50 p-3 rounded-xl border border-slate-800"><div class="text-slate-500 text-[10px] uppercase">{k}</div><div class="text-lg font-bold text-pink-500">{int(v * 100)}%</div></div>' for k, v in taste_profile.profile['core_identity'].items())}
                    </div>
                </div>
                <div class="glass-card p-8 rounded-[2rem]">
                    <h2 class="text-amber-500 font-bold uppercase text-[10px] tracking-widest mb-6">Current Vibe Intensity</h2>
                    <div class="space-y-4">
                        {"".join(f'''
                            <div class="flex items-center gap-4">
                                <div class="text-sm font-medium w-32">{k}</div>
                                <div class="flex-1 bg-slate-800 h-2 rounded-full overflow-hidden"><div class="bg-amber-500 h-full" style="width: {v * 100}%"></div></div>
                                <div class="text-xs font-mono text-slate-500">{v}</div>
                            </div>
                        ''' for k, v in taste_profile.profile['current_vibe'].items())}
                    </div>
                </div>
            </div>

            <section class="glass-card p-10 rounded-[2rem]">
                <h2 class="text-slate-500 font-bold uppercase text-[10px] tracking-widest mb-10">Taste Evolution ({len(taste_profile.profile['taste_timeline'])} Eras)</h2>
                <div class="ml-6 border-l border-slate-800 pl-10 space-y-12">
                    {"".join(f'''
                        <div class="timeline-dot">
                            <div class="flex flex-col md:flex-row md:justify-between mb-2">
                                <h3 class="text-lg font-bold text-white">{era['era_label']}</h3>
                                <span class="text-xs font-mono text-slate-500">{era['time_range']}</span>
                            </div>
                            <div class="flex flex-wrap gap-2 mb-4">
                                {"".join(f'<span class="text-[10px] bg-slate-800 px-2 py-0.5 rounded text-slate-400 border border-slate-700">{mood}</span>' for mood in era['dominant_moods'])}
                            </div>
                            <div class="grid grid-cols-2 md:grid-cols-5 gap-4">
                                {"".join(f'<div class="text-center bg-slate-900/30 p-2 rounded-lg"><div class="text-[9px] uppercase text-slate-600 tracking-tighter">{tk}</div><div class="text-xs font-bold text-sky-400">{tv}</div></div>' for tk, tv in era['technical_fingerprint'].items())}
                            </div>
                        </div>
                    ''' for era in taste_profile.profile['taste_timeline'])}
                </div>
            </section>

            <footer class="flex flex-col md:flex-row justify-between text-[9px] uppercase tracking-[0.3em] text-slate-600 border-t border-slate-900 pt-8 px-4">
                <div class="flex gap-6">
                    <span>Logic: {taste_profile.logic_version}</span>
                    <span>Profiler: {taste_profile.profiler}</span>
                </div>
                <div class="flex gap-6 mt-4 md:mt-0">
                    <span>Reflect Model: {taste_profile.profiler_metadata.get('models', {}).get('reflect', 'N/A')}</span>
                    <span>Updated: {taste_profile.updated_at}</span>
                </div>
            </footer>
        </div>
    </body>
    </html>
    """
    # fmt: on


def generate_profile_html_file(output: str) -> Path:
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as temp_file:
        temp_file.write(output.encode("utf-8"))
        return Path(temp_file.name)
