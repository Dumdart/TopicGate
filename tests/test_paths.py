from pathlib import Path

from topicgate.paths import prepare_database_path, sqlite_url


def test_fresh_installation_uses_new_database_path(tmp_path: Path) -> None:
    target = prepare_database_path(tmp_path / "data")

    assert target == tmp_path / "data" / "topicgate.db"
    assert not target.exists()
