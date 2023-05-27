"""boyadl CLI."""
import json
import re
from io import BytesIO
from urllib.request import urlopen

import typer
from pydub import AudioSegment


app = typer.Typer()

def _download_audio(lesson_name:str, url: str) -> None:
    buffer = BytesIO(urlopen(url).read())
    buffer.seek(0)
    AudioSegment.from_file(buffer).export(
        f"{lesson_name}.mp3", format="mp3", parameters=["-q:a", "0"]
    )

@app.command()  # type: ignore
def main(url: str) -> None:
    """Download mp3 files for Boya Chinese books.

    Args:
        url (str): The url found after scanning the QR code on the back cover of the book.

    Raises:
        Exit: If an error occurred.
    """
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
        _download_audio(lesson_name, url)


if __name__ == "__main__":
    app()
