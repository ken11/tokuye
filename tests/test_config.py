"""Tests for skills_dir config handling."""

import pytest
from pathlib import Path

from tokuye.utils.config import Settings, _apply_yaml_to_settings


class TestSkillsDirConfig:
    """skills_dir の config.yaml 反映と仕様確認。"""

    def _make_settings(self, project_root: Path) -> Settings:
        s = Settings()
        s.project_root = project_root
        return s

    def test_skills_dir_is_applied_from_yaml(self, tmp_path):
        """config.yaml に skills_dir を書いたら settings.skills_dir に反映される。"""
        s = self._make_settings(tmp_path)
        assert s.skills_dir is None  # デフォルトは None

        _apply_yaml_to_settings(s, {"skills_dir": ".tokuye/skills"})

        assert s.skills_dir == ".tokuye/skills"

    def test_skills_dir_not_set_defaults_to_none(self, tmp_path):
        """skills_dir を yaml に書かなければ None のまま。"""
        s = self._make_settings(tmp_path)
        _apply_yaml_to_settings(s, {"language": "ja"})

        assert s.skills_dir is None

    def test_skills_dir_null_in_yaml(self, tmp_path):
        """yaml で null を指定した場合は None になる（bundled にフォールバック）。"""
        s = self._make_settings(tmp_path)
        s.skills_dir = ".tokuye/skills"  # 一度セット

        _apply_yaml_to_settings(s, {"skills_dir": None})

        assert s.skills_dir is None

    def test_skills_dir_empty_string_in_yaml(self, tmp_path):
        """yaml で空文字を指定した場合は空文字になる（bundled にフォールバック）。"""
        s = self._make_settings(tmp_path)
        _apply_yaml_to_settings(s, {"skills_dir": ""})

        # 空文字は falsy なので _build_skills_plugin では bundled にフォールバックする
        assert s.skills_dir == ""

    def test_skills_dir_absolute_path(self, tmp_path):
        """絶対パスも文字列のまま反映される。"""
        s = self._make_settings(tmp_path)
        abs_path = str(tmp_path / "my-skills")

        _apply_yaml_to_settings(s, {"skills_dir": abs_path})

        assert s.skills_dir == abs_path

    def test_skills_dir_does_not_affect_other_keys(self, tmp_path):
        """skills_dir の追加が他のキーの反映を壊していない。"""
        s = self._make_settings(tmp_path)
        _apply_yaml_to_settings(s, {"language": "ja", "skills_dir": ".tokuye/skills"})

        assert s.language == "ja"
        assert s.skills_dir == ".tokuye/skills"


class TestBuildSkillsPluginFallback:
    """_build_skills_plugin の bundled フォールバック動作確認。"""

    def test_bundled_skills_dir_exists(self):
        """パッケージ同梱の skills ディレクトリが存在する。"""
        from tokuye.agent.strands_agent import _build_skills_plugin
        import tokuye

        bundled = Path(tokuye.__file__).parent / "skills"
        assert bundled.exists(), f"bundled skills dir not found: {bundled}"

    def test_build_skills_plugin_returns_plugin_when_bundled_exists(self, tmp_path, monkeypatch):
        """skills_dir 未設定でも bundled が存在すれば AgentSkills を返す。"""
        from tokuye.utils.config import settings as _settings
        from tokuye.agent import strands_agent as sa

        monkeypatch.setattr(_settings, "skills_dir", None)
        monkeypatch.setattr(_settings, "project_root", tmp_path)

        plugin = sa._build_skills_plugin()
        # bundled skills dir が存在する限り None にならない
        assert plugin is not None

    def test_build_skills_plugin_uses_configured_dir_when_exists(self, tmp_path, monkeypatch):
        """skills_dir に存在するパスを指定したらそちらを使う。"""
        from tokuye.utils.config import settings as _settings
        from tokuye.agent import strands_agent as sa

        custom_skills = tmp_path / "my-skills"
        custom_skills.mkdir()

        monkeypatch.setattr(_settings, "skills_dir", str(custom_skills))
        monkeypatch.setattr(_settings, "project_root", tmp_path)

        plugin = sa._build_skills_plugin()
        assert plugin is not None

    def test_build_skills_plugin_falls_back_to_bundled_when_dir_missing(self, tmp_path, monkeypatch):
        """skills_dir に存在しないパスを指定したら bundled にフォールバックする。"""
        from tokuye.utils.config import settings as _settings
        from tokuye.agent import strands_agent as sa

        monkeypatch.setattr(_settings, "skills_dir", str(tmp_path / "nonexistent"))
        monkeypatch.setattr(_settings, "project_root", tmp_path)

        # bundled が存在する限り None にならない（フォールバック成功）
        plugin = sa._build_skills_plugin()
        assert plugin is not None
