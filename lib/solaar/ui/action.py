## Copyright (C) 2012-2013  Daniel Pavel
## Copyright (C) 2014-2024  Solaar Contributors https://pwr-solaar.github.io/Solaar/
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License along
## with this program; if not, write to the Free Software Foundation, Inc.,
## 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
import logging
import traceback
from enum import Enum

import yaml
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk

from logitech_receiver.hidpp20 import OnboardProfiles
from logitech_receiver.hidpp20 import OnboardProfilesVersion
from solaar.i18n import _
from solaar.ui import common

from . import pair_window

logger = logging.getLogger(__name__)


class GtkSignal(Enum):
    ACTIVATE = "activate"


def make_image_menu_item(label, icon_name, function, *args):
    box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 6)
    label = Gtk.Label(label=label)
    icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.LARGE_TOOLBAR) if icon_name is not None else Gtk.Image()
    box.add(icon)
    box.add(label)
    menu_item = Gtk.MenuItem()
    menu_item.add(box)
    menu_item.show_all()
    menu_item.connect(GtkSignal.ACTIVATE.value, function, *args)
    menu_item.label = label
    menu_item.icon = icon
    return menu_item


def make(name, label, function, stock_id=None, *args):
    action = Gtk.Action(name=name, label=label, tooltip=label, stock_id=None)
    action.set_icon_name(name)
    if stock_id is not None:
        action.set_stock_id(stock_id)
    if function:
        action.connect(GtkSignal.ACTIVATE.value, function, *args)
    return action


def make_toggle(name, label, function, stock_id=None, *args):
    action = Gtk.ToggleAction(name=name, label=label, tooltip=label, stock_id=None)
    action.set_icon_name(name)
    if stock_id is not None:
        action.set_stock_id(stock_id)
    action.connect(GtkSignal.ACTIVATE.value, function, *args)
    return action


def pair(window, receiver):
    assert receiver
    assert receiver.kind is None

    pair_dialog = pair_window.create(receiver)
    pair_dialog.set_transient_for(window)
    pair_dialog.set_destroy_with_parent(True)
    pair_dialog.set_modal(True)
    pair_dialog.set_type_hint(Gdk.WindowTypeHint.DIALOG)
    pair_dialog.set_position(Gtk.WindowPosition.CENTER)
    pair_dialog.present()


def unpair(window, device):
    assert device
    assert device.kind is not None

    qdialog = Gtk.MessageDialog(
        transient_for=window,
        flags=0,
        message_type=Gtk.MessageType.QUESTION,
        buttons=Gtk.ButtonsType.NONE,
        text=_("Unpair") + " " + device.name + " ?",
    )
    qdialog.set_icon_name("remove")
    qdialog.add_button(_("Cancel"), Gtk.ResponseType.CANCEL)
    qdialog.add_button(_("Unpair"), Gtk.ResponseType.ACCEPT)
    choice = qdialog.run()
    qdialog.destroy()
    if choice == Gtk.ResponseType.ACCEPT:
        receiver = device.receiver
        assert receiver
        device_number = device.number

        try:
            del receiver[device_number]
        except Exception:
            common.error_dialog(common.ErrorReason.UNPAIR, device)


def _show_message(window, title, text, message_type):
    """Helper to show a message dialog"""
    dialog = Gtk.MessageDialog(
        parent=window, flags=Gtk.DialogFlags.MODAL, type=message_type, buttons=Gtk.ButtonsType.OK, text=title
    )
    dialog.format_secondary_text(text)
    dialog.run()
    dialog.destroy()


def export_profiles(window, device):
    """Export device onboard profiles to YAML file"""
    assert device
    assert device.kind is not None

    if not device.online:
        common.error_dialog(common.ErrorReason.NO_DEVICE, device.name)
        return

    if device.profiles is None:
        _show_message(
            window, _("No Profiles"), _("Device %s does not support onboard profiles.") % device.name, Gtk.MessageType.WARNING
        )
        return

    # Create file chooser dialog
    dialog = Gtk.FileChooserDialog(title=_("Export Profiles"), parent=window, action=Gtk.FileChooserAction.SAVE)
    dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK)

    # Set default filename
    default_name = f"{device.name.replace(' ', '_')}_profiles.yaml"
    dialog.set_current_name(default_name)

    # Add YAML filter
    filter_yaml = Gtk.FileFilter()
    filter_yaml.set_name(_("YAML files"))
    filter_yaml.add_pattern("*.yaml")
    dialog.add_filter(filter_yaml)

    # Add all files filter
    filter_all = Gtk.FileFilter()
    filter_all.set_name(_("All files"))
    filter_all.add_pattern("*")
    dialog.add_filter(filter_all)

    response = dialog.run()
    filename = dialog.get_filename()
    dialog.destroy()

    if response == Gtk.ResponseType.OK and filename:

        def _do_export():
            try:
                with open(filename, "w") as f:
                    yaml.dump(device.profiles, f)

                GLib.idle_add(
                    _show_message,
                    window,
                    _("Export Successful"),
                    _("Successfully exported profiles to:\n%s") % filename,
                    Gtk.MessageType.INFO,
                )
            except Exception as e:
                logger.error("Error exporting profiles: %s", traceback.format_exc())
                GLib.idle_add(
                    _show_message, window, _("Export Failed"), _("Failed to export profiles:\n%s") % str(e), Gtk.MessageType.ERROR
                )

        common.ui_async(_do_export)


def import_profiles(window, device):
    """Import device onboard profiles from YAML file"""
    assert device
    assert device.kind is not None

    if not device.online:
        common.error_dialog(common.ErrorReason.NO_DEVICE, device.name)
        return

    if device.profiles is None:
        _show_message(
            window, _("No Profiles"), _("Device %s does not support onboard profiles.") % device.name, Gtk.MessageType.WARNING
        )
        return

    # Create file chooser dialog
    dialog = Gtk.FileChooserDialog(title=_("Import Profiles"), parent=window, action=Gtk.FileChooserAction.OPEN)
    dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, Gtk.STOCK_OPEN, Gtk.ResponseType.OK)

    # Add YAML filter
    filter_yaml = Gtk.FileFilter()
    filter_yaml.set_name(_("YAML files"))
    filter_yaml.add_pattern("*.yaml")
    dialog.add_filter(filter_yaml)

    # Add all files filter
    filter_all = Gtk.FileFilter()
    filter_all.set_name(_("All files"))
    filter_all.add_pattern("*")
    dialog.add_filter(filter_all)

    response = dialog.run()
    filename = dialog.get_filename()
    dialog.destroy()

    if response == Gtk.ResponseType.OK and filename:

        def _do_import():
            try:
                # Read and validate profiles file
                with open(filename, "r") as f:
                    profiles = yaml.safe_load(f)

                if not isinstance(profiles, OnboardProfiles):
                    raise ValueError(_("Invalid profiles file format"))

                if getattr(profiles, "version", None) != OnboardProfilesVersion:
                    version = getattr(profiles, "version", None)
                    raise ValueError(_("Profile version mismatch. Expected %d, got %s") % (OnboardProfilesVersion, version))

                # Optional: Warn if device name differs but allow import
                if getattr(profiles, "name", None) != device.name:
                    name = getattr(profiles, "name", None)
                    logger.warning("Profile device name '%s' differs from current device '%s'", name, device.name)

                # Write to device
                written = profiles.write(device)

                GLib.idle_add(
                    _show_message,
                    window,
                    _("Import Successful"),
                    _("Successfully imported profiles.\nWrote %d sectors to %s.") % (written, device.name),
                    Gtk.MessageType.INFO,
                )

            except Exception as e:
                logger.error("Error importing profiles: %s", traceback.format_exc())
                GLib.idle_add(
                    _show_message, window, _("Import Failed"), _("Failed to import profiles:\n%s") % str(e), Gtk.MessageType.ERROR
                )

        common.ui_async(_do_import)


def edit_profiles(window, device):
    """Open profile editor dialog"""
    assert device
    assert device.kind is not None

    if not device.online:
        common.error_dialog(common.ErrorReason.NO_DEVICE, device.name)
        return

    if device.profiles is None:
        _show_message(
            window,
            _("No Profiles"),
            _("Device %s does not support onboard profiles.") % device.name,
            Gtk.MessageType.WARNING
        )
        return

    # Import profile editor module
    from . import profile_editor

    # Create and show editor
    profile_editor.create(device, window)
