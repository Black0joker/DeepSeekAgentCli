import os
import sys
from dotenv import load_dotenv
from app.agent.logger import Logger

class Config:
    """Validates and provides access to environment variables."""
    @staticmethod
    def _get_env_path():
        """Get the path to the .env file, supporting PyInstaller bundles."""
        if getattr(sys, 'frozen', False):
            # Running as PyInstaller bundle: .env is in app/agent/ inside MEIPASS
            base = os.path.join(sys._MEIPASS, 'app', 'agent')
        else:
            # Running as script: look relative to this file
            base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, '.env')
    
    @staticmethod
    def _get_external_env_path():
        """Get the path to an .env file placed next to the exe/script.
        
        Takes priority over the bundled .env so users can swap accounts without rebuilding.
        """
        if getattr(sys, 'frozen', False):
            # Running as exe: look next to the exe file
            return os.path.join(os.path.dirname(sys.executable), '.env')
        else:
            # Running as script: look in the current working directory
            return os.path.join(os.getcwd(), '.env')

    @staticmethod
    def load():
        # Priority: 1) External .env next to exe/script  2) Bundled .env  3) CWD / system env
        external_path = Config._get_external_env_path()
        bundled_path = Config._get_env_path()
        
        if os.path.exists(external_path):
            load_dotenv(external_path)
            Logger.info(f"Loaded .env from: {external_path} (external, overrides bundled)")
        elif os.path.exists(bundled_path):
            load_dotenv(bundled_path)
            Logger.info(f"Loaded .env from: {bundled_path} (bundled)")
        else:
            # Fallback: try current directory / system environment
            load_dotenv()
            Logger.info("Loaded .env from current directory or system environment")
        required_vars = ["DS_SMIDV2", "DS_SESSION_ID", "DS_AUTHORIZATION"]
        missing = [var for var in required_vars if not os.getenv(var)]
        
        if missing:
            Logger.error(f"Missing required environment variables: {', '.join(missing)}")
            raise EnvironmentError(f"Missing configuration: {', '.join(missing)}")
        
        Logger.success("Configuration loaded and validated.")

    @staticmethod
    def get_cookies():
        return {
            ".thumbcache_6b2e5483f9d858d7c661c5e276b6a6ae": os.getenv("DS_THUMBCACHE"),
            "smidV2": os.getenv("DS_SMIDV2"),
            # "aws-waf-token": os.getenv("DS_AWS_WAF_TOKEN"),
            "ds_session_id": os.getenv("DS_SESSION_ID"),
        }

    @staticmethod
    def get_headers():
        return {
            "authorization": os.getenv("DS_AUTHORIZATION"),
            'x-client-bundle-id': 'com.deepseek.chat',
            'x-client-locale': 'en_US',
            'x-client-platform': 'web',
            'x-client-timezone-offset': '10800',
            'x-client-version': '2.2.0',
        }