"""
LLM Configuration Loader

Loads LLM configuration from YAML file and environment variables.
"""

import os
import yaml
from typing import List, Dict, Any
import logging
from pathlib import Path

from .types import ModelConfig

logger = logging.getLogger(__name__)


class ConfigLoader:
    """
    Configuration loader for LLM models.

    Loads from YAML file and resolves environment variables.
    """

    def __init__(self, config_path: str = None):
        """
        Initialize config loader.

        Args:
            config_path: Path to YAML config file (default: backend/config/llm_config.yaml)
        """
        if config_path is None:
            # Default to config/llm_config.yaml in backend directory
            backend_dir = Path(__file__).parent.parent.parent
            config_path = backend_dir / "config" / "llm_config.yaml"

        self.config_path = Path(config_path)

        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        logger.info(f"Loading LLM config from: {self.config_path}")

    def load(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file.

        Returns:
            Dictionary of configuration
        """
        with open(self.config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # Resolve environment variables
        config = self._resolve_env_vars(config)

        return config

    def load_model_configs(self) -> List[ModelConfig]:
        """
        Load model configurations.

        Returns:
            List of ModelConfig objects
        """
        config = self.load()

        model_configs = []

        for model_dict in config.get("models", []):
            # Skip disabled models
            if not model_dict.get("enabled", True):
                logger.info(f"Skipping disabled model: {model_dict.get('name')}")
                continue

            # Create ModelConfig
            try:
                model_config = ModelConfig(
                    name=model_dict["name"],
                    adapter_type=model_dict["adapter_type"],
                    api_key=model_dict["api_key"],
                    base_url=model_dict["base_url"],
                    model_id=model_dict["model_id"],
                    max_tokens=model_dict.get("max_tokens", 4000),
                    temperature=model_dict.get("temperature", 0.7),
                    timeout=model_dict.get("timeout", 60),
                    enabled=model_dict.get("enabled", True),
                    priority=model_dict.get("priority", 99),
                    cost_per_1k_tokens=model_dict.get("cost_per_1k_tokens", 0.0),
                )

                model_configs.append(model_config)
                logger.info(
                    f"Loaded model config: {model_config.name} "
                    f"(priority={model_config.priority})"
                )

            except KeyError as e:
                logger.error(
                    f"Invalid model config for {model_dict.get('name')}: "
                    f"missing field {e}"
                )
                continue

        if not model_configs:
            raise ValueError("No enabled models found in configuration")

        # Sort by priority
        model_configs.sort(key=lambda x: x.priority)

        return model_configs

    def get_router_config(self) -> Dict[str, Any]:
        """
        Get router configuration.

        Returns:
            Router config dictionary
        """
        config = self.load()
        return config.get("router", {})

    def get_rag_config(self) -> Dict[str, Any]:
        """
        Get RAG configuration.

        Returns:
            RAG config dictionary
        """
        config = self.load()
        return config.get("rag", {})

    def get_context_config(self) -> Dict[str, Any]:
        """
        Get context management configuration.

        Returns:
            Context config dictionary
        """
        config = self.load()
        return config.get("context", {})

    def _resolve_env_vars(self, config: Any) -> Any:
        """
        Recursively resolve environment variables in config.

        Supports ${VAR_NAME} syntax with fallback to config.py values.

        Args:
            config: Config dict or value

        Returns:
            Config with resolved env vars
        """
        if isinstance(config, dict):
            return {k: self._resolve_env_vars(v) for k, v in config.items()}
        elif isinstance(config, list):
            return [self._resolve_env_vars(item) for item in config]
        elif isinstance(config, str):
            # Check for ${VAR_NAME} pattern
            if config.startswith("${") and config.endswith("}"):
                var_name = config[2:-1]
                value = os.getenv(var_name)

                if value is None:
                    # Fallback to config.py values
                    fallback_value = self._get_fallback_value(var_name)
                    if fallback_value:
                        logger.info(
                            f"Environment variable '{var_name}' not set, "
                            f"using fallback from config.py"
                        )
                        return fallback_value
                    else:
                        logger.warning(
                            f"Environment variable '{var_name}' not set and no fallback available, "
                            f"using placeholder"
                        )
                        return f"MISSING_{var_name}"

                return value

        return config

    def _get_fallback_value(self, var_name: str) -> str:
        """
        Get fallback value from questionExtract.config if available.

        Args:
            var_name: Environment variable name

        Returns:
            Fallback value or None
        """
        try:
            from questionExtract.config import QWEN_API_KEY, QWEN_BASE_URL

            if var_name == "QWEN_API_KEY":
                return QWEN_API_KEY
            elif var_name == "QWEN_BASE_URL":
                return QWEN_BASE_URL
        except ImportError:
            pass

        return None


# Singleton instance
_config_loader = None


def get_config_loader() -> ConfigLoader:
    """
    Get singleton config loader instance.

    Returns:
        ConfigLoader instance
    """
    global _config_loader

    if _config_loader is None:
        _config_loader = ConfigLoader()

    return _config_loader
