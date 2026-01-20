import os
import yaml
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file

class Config:
    "Configuration loader"
    # ============ SECRETS FROM .ENV ============
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

    # ============ LOAD YAML CONFIG ============
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    CONFIG_PATH = os.path.join(BASE_DIR, 'core', 'config.yaml')

    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            _config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        _config = {}
        
    # ============ GENERAL CONFIG ============
    BASE_MODEL = _config["models"]['base_model']
    BASE_TEMPERATURE = _config["models"]['base_temperature']
        
    # ============ VALIDATION ============
    @classmethod
    def validate(cls):
        """Check if all required secrets are loaded"""
        required_secrets = [
            'OPENAI_API_KEY',
        ]
        
        missing = []
        for secret in required_secrets:
            if not getattr(cls, secret):
                missing.append(secret)
        
        if missing:
            raise ValueError(f"❌ Missing required secrets in .env: {missing}")
        
        print("✅ All configuration loaded successfully!")
        print(f"   Model: {cls.BASE_MODEL}")


# Validate on import
Config.validate()