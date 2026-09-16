# PyInstaller runtime hook: keep the Windows client resilient when the production
# backend is temporarily behind and use the hardened self-update handoff before
# application modules import those entrypoints.
import core
from instagram_fallback import patch_api_client
from windows_updater import patch_windows_updater

patch_api_client(core)
patch_windows_updater(core)
