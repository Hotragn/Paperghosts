"""config reads the environment first, then .env, and knows both Ultramarine key names."""

from paperghosts import config


def test_env_file_lines(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "# a comment = with an equals sign\n"
        "\n"
        "PLAIN=abc\n"
        " SPACED = abc def \n"
        "URI=mongodb+srv://u:p@h/?a=b&c=d\n"
        'DOUBLE="quoted value"\n'
        "SINGLE='quoted'\n"
        "EMPTY=\n"
        "no equals sign\n"
    )
    assert config.read_env_file(env) == {
        "PLAIN": "abc",
        "SPACED": "abc def",
        "URI": "mongodb+srv://u:p@h/?a=b&c=d",
        "DOUBLE": "quoted value",
        "SINGLE": "quoted",
        "EMPTY": "",
    }
    assert config.read_env_file(tmp_path / "missing") == {}  # Render has no .env


def test_setting_reads_environment_then_env_file_then_alias(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "SERPAPI_API_KEY=from-file\nPAPERINSTRUMENTS_API_KEY=from-file\nHF_TOKEN=\n"
    )
    monkeypatch.setattr(config, "ENV_FILE", env)
    for name in (
        "SERPAPI_API_KEY",
        "ULTRAMARINE_API_KEY",
        "PAPERINSTRUMENTS_API_KEY",
        "HF_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("SERPAPI_API_KEY", "from-env")

    assert config.setting("SERPAPI_API_KEY").get() == "from-env"
    assert config.setting("ULTRAMARINE_API_KEY").get() == "from-file"
    assert not config.setting("HF_TOKEN")
