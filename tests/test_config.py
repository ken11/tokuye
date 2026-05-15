"""Tests for skills_dir config handling."""

from pathlib import Path

from tokuye.utils.config import Settings, _apply_yaml_to_settings


class TestSkillsDirConfig:
    """Verify that skills_dir is correctly reflected from config.yaml."""

    def _make_settings(self, project_root: Path) -> Settings:
        s = Settings()
        s.project_root = project_root
        return s

    def test_skills_dir_is_applied_from_yaml(self, tmp_path):
        """skills_dir written in config.yaml is reflected in settings.skills_dir."""
        s = self._make_settings(tmp_path)
        assert s.skills_dir is None  # default is None

        _apply_yaml_to_settings(s, {"skills_dir": ".tokuye/skills"})

        assert s.skills_dir == ".tokuye/skills"

    def test_skills_dir_not_set_defaults_to_none(self, tmp_path):
        """skills_dir stays None when not present in yaml."""
        s = self._make_settings(tmp_path)
        _apply_yaml_to_settings(s, {"language": "ja"})

        assert s.skills_dir is None

    def test_skills_dir_null_in_yaml(self, tmp_path):
        """null in yaml results in None, which falls back to bundled skills."""
        s = self._make_settings(tmp_path)
        s.skills_dir = ".tokuye/skills"  # set a value first

        _apply_yaml_to_settings(s, {"skills_dir": None})

        assert s.skills_dir is None

    def test_skills_dir_empty_string_in_yaml(self, tmp_path):
        """Empty string in yaml is stored as-is; _build_skills_plugin treats it as falsy and falls back to bundled."""
        s = self._make_settings(tmp_path)
        _apply_yaml_to_settings(s, {"skills_dir": ""})

        assert s.skills_dir == ""

    def test_skills_dir_absolute_path(self, tmp_path):
        """Absolute path is stored as a string without modification."""
        s = self._make_settings(tmp_path)
        abs_path = str(tmp_path / "my-skills")

        _apply_yaml_to_settings(s, {"skills_dir": abs_path})

        assert s.skills_dir == abs_path

    def test_skills_dir_does_not_affect_other_keys(self, tmp_path):
        """Adding skills_dir to simple_keys does not break other key reflection."""
        s = self._make_settings(tmp_path)
        _apply_yaml_to_settings(s, {"language": "ja", "skills_dir": ".tokuye/skills"})

        assert s.language == "ja"
        assert s.skills_dir == ".tokuye/skills"


class TestBuildSkillsPluginFallback:
    """Verify _build_skills_plugin bundled fallback behaviour."""

    def test_bundled_skills_dir_exists(self):
        """The bundled skills directory shipped with the package exists."""
        import tokuye

        bundled = Path(tokuye.__file__).parent / "skills"
        assert bundled.exists(), f"bundled skills dir not found: {bundled}"

    def test_build_skills_plugin_returns_plugin_when_bundled_exists(self, tmp_path, monkeypatch):
        """Returns an AgentSkills instance even when skills_dir is not configured."""
        from tokuye.utils.config import settings as _settings
        from tokuye.agent import strands_agent as sa

        monkeypatch.setattr(_settings, "skills_dir", None)
        monkeypatch.setattr(_settings, "project_root", tmp_path)

        plugin = sa._build_skills_plugin()
        # bundled skills dir exists, so the result must not be None
        assert plugin is not None

    def test_build_skills_plugin_uses_configured_dir_when_exists(self, tmp_path, monkeypatch):
        """Uses the configured skills_dir when it exists on disk."""
        from tokuye.utils.config import settings as _settings
        from tokuye.agent import strands_agent as sa

        custom_skills = tmp_path / "my-skills"
        custom_skills.mkdir()

        monkeypatch.setattr(_settings, "skills_dir", str(custom_skills))
        monkeypatch.setattr(_settings, "project_root", tmp_path)

        plugin = sa._build_skills_plugin()
        assert plugin is not None

    def test_build_skills_plugin_falls_back_to_bundled_when_dir_missing(self, tmp_path, monkeypatch):
        """Falls back to bundled skills when the configured skills_dir does not exist."""
        from tokuye.utils.config import settings as _settings
        from tokuye.agent import strands_agent as sa

        monkeypatch.setattr(_settings, "skills_dir", str(tmp_path / "nonexistent"))
        monkeypatch.setattr(_settings, "project_root", tmp_path)

        # bundled exists, so fallback succeeds and plugin is not None
        plugin = sa._build_skills_plugin()
        assert plugin is not None
