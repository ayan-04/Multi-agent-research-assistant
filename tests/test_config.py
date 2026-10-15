from src.config import Settings, load_settings


def test_defaults_are_free_tier_caps():
    settings = Settings()
    assert settings.gemini_model == "gemini-2.5-flash"
    assert settings.gemini_api_key == ""
    assert settings.max_llm_calls == 12
    assert settings.max_searches == 6
    assert settings.critic_max_iterations == 2


def test_trimmed_caps_critic_iterations():
    settings = Settings(critic_max_iterations=9, max_steps=0, chunk_overlap=5000, chunk_size=10)
    trimmed = settings.trimmed()
    assert trimmed.critic_max_iterations == 2
    assert trimmed.max_steps == 1
    assert trimmed.chunk_overlap == 5000


def test_load_settings_reads_env(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_MODEL=gemini-test\nMAX_LLM_CALLS=4\n", encoding="utf-8")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("MAX_LLM_CALLS", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    settings = load_settings(env_file)
    assert settings.gemini_model == "gemini-test"
    assert settings.max_llm_calls == 4
    assert settings.gemini_api_key == ""
