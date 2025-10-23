from configparser import ConfigParser
from pathlib import Path


def test_mypy_targets_entire_src_package() -> None:
    root_dir = Path(__file__).resolve().parents[2]
    config_path = root_dir / "mypy.ini"

    parser = ConfigParser()
    read_files = parser.read(config_path, encoding="utf-8")
    assert read_files, "mypy.ini が読み込めませんでした"

    assert parser.has_option("mypy", "files"), "[mypy] セクションに files オプションがありません"
    files_option = parser.get("mypy", "files").strip()

    assert (
        files_option == "src"
    ), f"mypy の files オプションが src を対象としていません: {files_option!r}"
