"""
Configuration of the GNOME desktop
========================================

Control the GNOME settings

.. code-block:: yaml

    localdesktop_wm_prefs:
        gnomedesktop.wm_preferences:
            - user: username
            - audible_bell: false
            - action_double_click_titlebar: 'toggle-maximize'
            - visual_bell: true
            - num_workspaces: 6
    localdesktop_lockdown:
        gnomedesktop.desktop_lockdown:
            - user: username
            - disable_user_switching: true
    localdesktop_interface:
        gnomedesktop.desktop_interface:
            - user: username
            - clock_show_date: true
            - clock_format: 12h
"""

import logging
import re

log = logging.getLogger(__name__)


def _check_current_value(gnome_kwargs, value):
    """
    Check the current value with the passed value
    """
    current_value = __salt__["gnome.get"](**gnome_kwargs)
    return str(current_value) == str(value)


def _do(name, gnome_kwargs, preferences):
    """
    worker function for the others to use
    this handles all the gsetting magic
    """
    ret = {"name": name, "result": True, "changes": {}, "comment": ""}

    messages = []

    for pref in preferences:
        key = pref
        value = preferences[pref]

        if isinstance(value, bool):
            ftype = "boolean"

            # need to convert boolean values to strings and make lowercase to
            # pass to gsettings
            value = str(value).lower()

        elif isinstance(value, int):
            ftype = "int"
        elif isinstance(value, str):
            ftype = "string"
        else:
            ftype = "string"

        gnome_kwargs.update({"key": key, "value": value})

        if _check_current_value(gnome_kwargs, value):
            messages.append(f"{key} is already set to {value}")
        else:
            result = __salt__["gnome.set"](**gnome_kwargs)
            if result["retcode"] == 0:
                messages.append(f"Setting {key} to {value}")
                ret["changes"][key] = f"{key}:{value}"
                ret["result"] = True
            else:
                messages.append(result["stdout"])
                ret["result"] = False

        ret["comment"] = ", ".join(messages)

    return ret


def wm_preferences(
    name,
    user=None,
    action_double_click_titlebar=None,
    action_middle_click_titlebar=None,
    action_right_click_titlebar=None,
    application_based=None,
    audible_bell=None,
    auto_raise=None,
    auto_raise_delay=None,
    button_layout=None,
    disable_workarounds=None,
    focus_mode=None,
    focus_new_windows=None,
    mouse_button_modifier=None,
    num_workspaces=None,
    raise_on_click=None,
    resize_with_right_button=None,
    theme=None,
    titlebar_font=None,
    titlebar_uses_system_font=None,
    visual_bell=None,
    visual_bell_type=None,
    workspace_names=None,
    **kwargs,
):
    """
    wm_preferences: sets values in the org.gnome.desktop.wm.preferences schema
    """
    gnome_kwargs = {"user": user, "schema": "org.gnome.desktop.wm.preferences"}

    preferences = [
        "action_double_click_titlebar",
        "action_middle_click_titlebar",
        "action_right_click_titlebar",
        "application_based",
        "audible_bell",
        "auto_raise",
        "auto_raise_delay",
        "button_layout",
        "disable_workarounds",
        "focus_mode",
        "focus_new_windows",
        "mouse_button_modifier",
        "num_workspaces",
        "raise_on_click",
        "resize_with_right_button",
        "theme",
        "titlebar_font",
        "titlebar_uses_system_font",
        "visual_bell",
        "visual_bell_type",
        "workspace_names",
    ]

    preferences_hash = {}
    for pref in preferences:
        if pref in locals() and locals()[pref] is not None:
            key = re.sub("_", "-", pref)
            preferences_hash[key] = locals()[pref]

    return _do(name, gnome_kwargs, preferences_hash)


def desktop_lockdown(
    name,
    user=None,
    disable_application_handlers=None,
    disable_command_line=None,
    disable_lock_screen=None,
    disable_log_out=None,
    disable_print_setup=None,
    disable_printing=None,
    disable_save_to_disk=None,
    disable_user_switching=None,
    user_administration_disabled=None,
    **kwargs,
):
    """
    desktop_lockdown: sets values in the org.gnome.desktop.lockdown schema
    """
    gnome_kwargs = {"user": user, "schema": "org.gnome.desktop.lockdown"}

    preferences = [
        "disable_application_handlers",
        "disable_command_line",
        "disable_lock_screen",
        "disable_log_out",
        "disable_print_setup",
        "disable_printing",
        "disable_save_to_disk",
        "disable_user_switching",
        "user_administration_disabled",
    ]

    preferences_hash = {}
    for pref in preferences:
        if pref in locals() and locals()[pref] is not None:
            key = re.sub("_", "-", pref)
            preferences_hash[key] = locals()[pref]

    return _do(name, gnome_kwargs, preferences_hash)


def desktop_interface(
    name,
    user=None,
    automatic_mnemonics=None,
    buttons_have_icons=None,
    can_change_accels=None,
    clock_format=None,
    clock_show_date=None,
    clock_show_seconds=None,
    cursor_blink=None,
    cursor_blink_time=None,
    cursor_blink_timeout=None,
    cursor_size=None,
    cursor_theme=None,
    document_font_name=None,
    enable_animations=None,
    font_name=None,
    gtk_color_palette=None,
    gtk_color_scheme=None,
    gtk_im_module=None,
    gtk_im_preedit_style=None,
    gtk_im_status_style=None,
    gtk_key_theme=None,
    gtk_theme=None,
    gtk_timeout_initial=None,
    gtk_timeout_repeat=None,
    icon_theme=None,
    menubar_accel=None,
    menubar_detachable=None,
    menus_have_icons=None,
    menus_have_tearoff=None,
    monospace_font_name=None,
    show_input_method_menu=None,
    show_unicode_menu=None,
    text_scaling_factor=None,
    toolbar_detachable=None,
    toolbar_icons_size=None,
    toolbar_style=None,
    toolkit_accessibility=None,
    **kwargs,
):
    """
    desktop_interface: sets values in the org.gnome.desktop.interface schema
    """
    gnome_kwargs = {"user": user, "schema": "org.gnome.desktop.interface"}

    preferences = [
        "automatic_mnemonics",
        "buttons_have_icons",
        "can_change_accels",
        "clock_format",
        "clock_show_date",
        "clock_show_seconds",
        "cursor_blink",
        "cursor_blink_time",
        "cursor_blink_timeout",
        "cursor_size",
        "cursor_theme",
        "document_font_name",
        "enable_animations",
        "font_name",
        "gtk_color_palette",
        "gtk_color_scheme",
        "gtk_im_module",
        "gtk_im_preedit_style",
        "gtk_im_status_style",
        "gtk_key_theme",
        "gtk_theme",
        "gtk_timeout_initial",
        "gtk_timeout_repeat",
        "icon_theme",
        "menubar_accel",
        "menubar_detachable",
        "menus_have_icons",
        "menus_have_tearoff",
        "monospace_font_name",
        "show_input_method_menu",
        "show_unicode_menu",
        "text_scaling_factor",
        "toolbar_detachable",
        "toolbar_icons_size",
        "toolbar_style",
        "toolkit_accessibility",
    ]

    preferences_hash = {}
    for pref in preferences:
        if pref in locals() and locals()[pref] is not None:
            key = re.sub("_", "-", pref)
            preferences_hash[key] = locals()[pref]

    return _do(name, gnome_kwargs, preferences_hash)
