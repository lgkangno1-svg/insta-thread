# PyInstaller runtime hook: make the Windows client resilient when the production
# backend is temporarily behind by falling back to Instagram's public anonymous
# media endpoint for public posts only.
import core
from instagram_fallback import patch_api_client

patch_api_client(core)
