# PyInstaller runtime hook: keep the Windows client resilient when the production
# backend is temporarily behind and use the hardened self-update handoff before
# application modules import those entrypoints.
import core
from desktop_extras import collapse_redundant_thumbnails
from instagram_fallback import patch_api_client
from windows_updater import patch_windows_updater

_original_assets_from_response = core.assets_from_response


def _assets_from_response_without_duplicate_thumbnails(data):
    return collapse_redundant_thumbnails(_original_assets_from_response(data))


core.assets_from_response = _assets_from_response_without_duplicate_thumbnails
patch_api_client(core)
patch_windows_updater(core)
