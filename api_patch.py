"""
VRChat API client patch module.

VRChat regularly starts returning null for fields that the generated vrchatapi
models mark as required (e.g. `bio`, `current_avatar_asset_url`). The models then
raise "Invalid value for `x`, must not be `None`" while parsing the response and
login fails. Instead of patching fields one by one, this turns off the client-side
validation entirely, so an outdated library keeps working when the API changes.
"""
import logging
import vrchatapi

logger = logging.getLogger('vrchat_avatar_manager')


def make_configuration(**kwargs):
    """Create a vrchatapi Configuration with client-side validation disabled."""
    configuration = vrchatapi.Configuration(**kwargs)
    configuration.client_side_validation = False
    return configuration


def apply_patches():
    """
    Disable strict client-side validation for every model the library creates.
    Models that are parsed from API responses don't receive the ApiClient's
    configuration; they fall back to Configuration.get_default_copy(), so the
    default has to be changed as well.
    """
    logger.info("Applying VRChat API client patches")
    vrchatapi.Configuration.set_default(make_configuration())
    logger.info("VRChat API client patched: null fields from the API are accepted")
