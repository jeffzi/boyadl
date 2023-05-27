"""boyadl CLI."""
import json
import re
from io import BytesIO
from pathlib import Path
from urllib.request import urlopen

import typer
from pydub import AudioSegment
from typing_extensions import Annotated


app = typer.Typer(
    help="Download mp3 files for Boya Chinese books", add_completion=False
)
cwd = Path(".")


def _download_audio(url: str, filepath: Path) -> None:
    buffer = BytesIO(urlopen(url).read())
    buffer.seek(0)
    AudioSegment.from_file(buffer).export(
        filepath, format="mp3", parameters=["-q:a", "0"]
    )


@app.command()  # type: ignore
def main(
    url: str,
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            exists=True,
            file_okay=False,
            dir_okay=True,
            writable=True,
            resolve_path=True,
            help="Output directory",
        ),
    ] = cwd,
) -> None:
    """Download mp3 files for Boya Chinese books."""
    content = urlopen(url).read().decode()
    pattern = re.compile(r"^var data\s?=\s?(\{.*play_url.*http.*\})", re.MULTILINE)
    raw_data = pattern.findall(content)

    if not raw_data:
        typer.echo("List of lessons not found, did you pass the appropriate url?")
        raise typer.Exit(1)

    if len(raw_data) > 1:
        typer.echo("Ambiguous list of lessons, did you pass the appropriate url?")
        raise typer.Exit(1)

    data = json.loads(raw_data[0].replace("\\\\", "\\"))
    lessons = {
        lesson["item"]["title"]: lesson["item"]["play_url"]
        for lesson in data["tree_list"]
    }
    for lesson_name, url in lessons.items():
        _download_audio(url, output / f"{lesson_name}.mp3")


if __name__ == "__main__":
    app()
