"""boyadl CLI."""
import json
import multiprocessing
import re
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from multiprocessing.managers import DictProxy
from pathlib import Path
from urllib.request import urlopen

import httpx
import typer
from pydub import AudioSegment
from rich import console, live, panel, print, progress, spinner, text
from typing_extensions import Annotated


app = typer.Typer(
    help="Download mp3 files for Boya Chinese books", add_completion=False
)
cwd = Path(".")


def _download_audio(
    url: str,
    filepath: Path,
    task_updates: DictProxy,  # type: ignore[type-arg]
    task_id: progress.TaskID,
) -> None:
    buffer = BytesIO()

    with httpx.stream("GET", url) as response:
        total = int(response.headers["Content-Length"])
        task_updates[task_id] = {"completed": 0, "total": total}
        for chunk in response.iter_bytes():
            buffer.write(chunk)
            task_updates[task_id] = {
                "completed": response.num_bytes_downloaded,
                "total": total,
            }

    buffer.seek(0)
    AudioSegment.from_file(buffer).export(
        filepath, format="mp3", parameters=["-q:a", "0"]
    )


def _get_download_progress() -> progress.Progress:
    return progress.Progress(
        "{task.description}",
        "[progress.percentage]{task.percentage:>3.0f}%",
        progress.BarColumn(),
        progress.DownloadColumn(),
        progress.TransferSpeedColumn(),
        transient=True,
        auto_refresh=False,
    )


def _get_main_progress() -> progress.Progress:
    return progress.Progress(
        progress.MofNCompleteColumn(),
        progress.BarColumn(),
        progress.TimeElapsedColumn(),
        transient=True,
        auto_refresh=False,
    )


def _download_all_files(lessons: dict[str, str], output: Path, parallel: int) -> None:
    n_lessons = len(lessons)
    download_progress = _get_download_progress()
    main_progress = _get_main_progress()

    progress_group = console.Group(
        spinner.Spinner(
            "dots",
            text.Text.from_markup(
                f"[blue]Downloading [green]{n_lessons}[/green] files"
            ),
        ),
        main_progress,
        panel.Panel(download_progress),
    )

    futures = []
    with multiprocessing.Manager() as manager:
        task_updates = manager.dict()
        main_task = main_progress.add_task("Downloading:", total=n_lessons)

        with ThreadPoolExecutor(max_workers=parallel) as pool:
            for lesson_name, url in lessons.items():
                task_id = download_progress.add_task(lesson_name, visible=False)
                futures.append(
                    pool.submit(
                        _download_audio,
                        url,
                        output / f"{lesson_name}.mp3",
                        task_updates,
                        task_id,
                    )
                )

            with live.Live(progress_group, transient=True):
                while (
                    download_progress.tasks
                    and (n_finished := sum([future.done() for future in futures]))
                    < n_lessons
                ):
                    main_progress.update(main_task, completed=n_finished)

                    for task_id, status in task_updates.items():
                        completed = status["completed"]
                        total = status["total"]
                        download_progress.update(
                            task_id,
                            completed=completed,
                            total=total,
                            visible=completed < total,
                        )
                        if completed == total:
                            download_progress.remove_task(task_id)
                            task_updates.pop(task_id)

                    download_progress.refresh()
                    main_progress.refresh()
                    time.sleep(0.25)

            with live.Live(spinner.Spinner("dots", "Cleaning up"), transient=True):
                for future in futures:
                    future.result()


@app.command()  # type: ignore
def main(
    url: Annotated[str, typer.Argument(help="Url from QR code on the back cover.")],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            file_okay=False,
            dir_okay=True,
            writable=True,
            resolve_path=True,
            help="Output directory",
        ),
    ] = cwd,
    parallel: Annotated[int, typer.Option(help="Number of concurrent download.")] = 4,
) -> None:
    """Download mp3 files for Boya Chinese books."""
    content = urlopen(url).read().decode()
    pattern = re.compile(r"^var data\s?=\s?(\{.*play_url.*http.*\})", re.MULTILINE)
    raw_data = pattern.findall(content)

    if not raw_data:
        print("List of lessons not found, did you pass the appropriate url?")
        raise typer.Exit(1)

    if len(raw_data) > 1:
        print("Ambiguous list of lessons, did you pass the appropriate url?")
        raise typer.Exit(1)

    data = json.loads(raw_data[0].replace("\\\\", "\\"))
    lessons = {
        lesson["item"]["title"]: lesson["item"]["play_url"]
        for lesson in data["tree_list"]
    }

    output.mkdir(parents=True, exist_ok=True)
    _download_all_files(lessons, output, parallel)
    print(f"Downloaded {len(lessons)} mp3 files to {output.resolve()} ✨ 🍰 ✨")


if __name__ == "__main__":
    app()
