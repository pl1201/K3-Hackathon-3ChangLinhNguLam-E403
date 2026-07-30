import unittest

from coach.config import Settings


class SettingsTests(unittest.TestCase):
    def test_openai_is_default_provider(self) -> None:
        settings = Settings(
            _env_file=None,
            openai_api_key="openai-test-key",
            deepseek_api_key="deepseek-test-key",
        )
        self.assertEqual(settings.llm_provider, "openai")
        self.assertEqual(settings.llm_api_key, "openai-test-key")
        self.assertEqual(settings.llm_model, "gpt-4.1-mini")
        self.assertIsNone(settings.llm_base_url)

    def test_deepseek_provider_uses_its_own_configuration(self) -> None:
        settings = Settings(
            _env_file=None,
            enable_llm=True,
            llm_provider="deepseek",
            openai_api_key=None,
            deepseek_api_key="deepseek-test-key",
            deepseek_model="deepseek-chat",
        )
        self.assertTrue(settings.llm_enabled)
        self.assertEqual(settings.llm_api_key, "deepseek-test-key")
        self.assertEqual(settings.llm_model, "deepseek-chat")
        self.assertEqual(settings.llm_base_url, "https://api.deepseek.com")

    def test_provider_without_matching_key_uses_mock(self) -> None:
        settings = Settings(
            _env_file=None,
            llm_provider="deepseek",
            openai_api_key="openai-test-key",
            deepseek_api_key=None,
        )
        self.assertFalse(settings.llm_enabled)


if __name__ == "__main__":
    unittest.main()
