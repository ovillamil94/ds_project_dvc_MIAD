
from pathlib import Path
import yaml

# Project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Default configuration in the project root
DEFAULT_CONFIG = PROJECT_ROOT / "config.yml"


def load_config(config_path=None):
    """
    Load the YAML configuration file.
    Uses root config.yml by default.
    """
    path = Path(config_path) if config_path else DEFAULT_CONFIG

    # Resolve relative paths from project root
    if not path.is_absolute():
        path = PROJECT_ROOT / path

    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
