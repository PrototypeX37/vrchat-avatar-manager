"""
VRChat API client patch module.
This module patches the vrchatapi package to handle None values for current_avatar_asset_url.
"""
import logging
from vrchatapi.models.current_user import CurrentUser

logger = logging.getLogger('vrchat_avatar_manager')

def apply_patches():
    """
    Apply monkey patches to the vrchatapi package to handle API changes.
    """
    logger.info("Applying VRChat API client patches")
    
    # Direct patch of the property setter by replacing it completely
    # We need to find where the property is defined
    property_dict = CurrentUser.__dict__
    
    # Store original getter
    original_getter = property_dict['current_avatar_asset_url'].fget
    
    # Define a patched setter that allows None values
    def patched_setter(self, current_avatar_asset_url):
        if current_avatar_asset_url is None:
            logger.warning("Received None for current_avatar_asset_url, using empty string instead")
            self._current_avatar_asset_url = ""
        else:
            # Regular behavior - store the value directly
            self._current_avatar_asset_url = current_avatar_asset_url
    
    # Create and apply the patched property
    patched_property = property(original_getter, patched_setter)
    setattr(CurrentUser, 'current_avatar_asset_url', patched_property)
    
    logger.info("VRChat API client patches applied successfully - current_avatar_asset_url property patched")
