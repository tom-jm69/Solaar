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

from gi.repository import Gtk

from solaar.i18n import _
from solaar.ui import common

logger = logging.getLogger(__name__)


def create(device, parent_window):
    """Create and show the profile editor dialog"""
    editor = ProfileEditorDialog(device, parent_window)
    editor.show()
    return editor


class ProfileEditorDialog:
    def __init__(self, device, parent_window):
        self.device = device
        self.profiles = device.profiles
        self.current_profile_num = None
        self.modified = False
        self._ignore_changes = 0

        # Create dialog
        self.dialog = Gtk.Dialog(
            title=_("Onboard Profile Editor - %s") % device.name, parent=parent_window, flags=Gtk.DialogFlags.MODAL
        )
        self.dialog.set_default_size(700, 500)
        self.dialog.set_border_width(10)

        # Build UI
        self._build_ui()
        self._populate_profile_list()

        # Connect dialog signals
        self.dialog.connect("delete-event", self._on_delete)

    def _build_ui(self):
        """Build the dialog UI"""
        content_area = self.dialog.get_content_area()

        # Main horizontal box for split layout
        main_hbox = Gtk.HBox(spacing=10)
        content_area.pack_start(main_hbox, True, True, 0)

        # Left panel: Profile list
        self._create_profile_list(main_hbox)

        # Right panel: Edit fields
        self._create_edit_panel(main_hbox)

        # Bottom button bar
        button_box = self.dialog.get_action_area()
        button_box.set_layout(Gtk.ButtonBoxStyle.END)

        cancel_button = Gtk.Button.new_with_label(_("Cancel"))
        cancel_button.connect("clicked", self._on_cancel)
        button_box.pack_start(cancel_button, False, False, 0)

        self.save_button = Gtk.Button.new_with_label(_("Save to Device"))
        self.save_button.get_style_context().add_class("suggested-action")
        self.save_button.set_sensitive(False)
        self.save_button.connect("clicked", self._on_save)
        button_box.pack_start(self.save_button, False, False, 0)

    def _create_profile_list(self, parent):
        """Create scrolled TreeView with profile list"""
        # Scrolled window
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.set_size_request(200, 0)
        parent.pack_start(sw, False, True, 0)

        # TreeView model: [profile_number, profile_name, enabled_str]
        self.profile_store = Gtk.ListStore(int, str, str)
        self.profile_view = Gtk.TreeView(model=self.profile_store)
        self.profile_view.set_headers_visible(False)

        # Column: Profile name + enabled indicator
        renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Profile", renderer)

        def format_profile(column, cell, model, iter, data):
            profile_num = model.get_value(iter, 0)
            profile_name = model.get_value(iter, 1)
            enabled_str = model.get_value(iter, 2)
            cell.set_property("text", f"{profile_name} {enabled_str}")

        column.set_cell_data_func(renderer, format_profile)
        self.profile_view.append_column(column)

        # Selection signal
        selection = self.profile_view.get_selection()
        selection.connect("changed", self._on_profile_selected)

        sw.add(self.profile_view)

    def _create_edit_panel(self, parent):
        """Create Grid with edit fields"""
        # Scrolled window for edit panel
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        parent.pack_start(sw, True, True, 0)

        # Grid for form fields
        grid = Gtk.Grid()
        grid.set_row_spacing(10)
        grid.set_column_spacing(10)
        grid.set_margin_start(10)
        grid.set_margin_end(10)
        sw.add(grid)

        row = 0

        # Profile name
        label = Gtk.Label(label=_("Profile Name:"), halign=Gtk.Align.END)
        grid.attach(label, 0, row, 1, 1)

        self.name_entry = Gtk.Entry()
        self.name_entry.set_max_length(24)
        self.name_entry.set_hexpand(True)
        self.name_entry.connect("changed", self._on_field_changed)
        grid.attach(self.name_entry, 1, row, 2, 1)

        row += 1

        # Enabled switch
        label = Gtk.Label(label=_("Enabled:"), halign=Gtk.Align.END)
        grid.attach(label, 0, row, 1, 1)

        self.enabled_switch = Gtk.Switch(halign=Gtk.Align.START)
        self.enabled_switch.connect("notify::active", self._on_field_changed)
        grid.attach(self.enabled_switch, 1, row, 1, 1)

        row += 1

        # Separator
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.set_margin_top(10)
        sep.set_margin_bottom(10)
        grid.attach(sep, 0, row, 3, 1)

        row += 1

        # DPI Settings header
        label = Gtk.Label(label=_("<b>DPI Settings</b>"), halign=Gtk.Align.START, use_markup=True)
        grid.attach(label, 0, row, 3, 1)

        row += 1

        # Column headers for DPI table
        header_label = Gtk.Label(label=_("DPI Value"), halign=Gtk.Align.CENTER)
        grid.attach(header_label, 1, row, 1, 1)

        header_label2 = Gtk.Label(label=_("Default"), halign=Gtk.Align.CENTER)
        grid.attach(header_label2, 2, row, 1, 1)

        header_label3 = Gtk.Label(label=_("Shift"), halign=Gtk.Align.CENTER)
        grid.attach(header_label3, 3, row, 1, 1)

        row += 1

        # 5 DPI values with radio buttons
        self.dpi_spinners = []
        self.default_radios = []
        self.shift_radios = []

        for i in range(5):
            # DPI label
            label = Gtk.Label(label=f"DPI {i+1}:", halign=Gtk.Align.END)
            grid.attach(label, 0, row, 1, 1)

            # DPI spinner
            spinner = Gtk.SpinButton.new_with_range(100, 25600, 50)
            spinner.set_hexpand(True)
            spinner.connect("value-changed", self._on_field_changed)
            self.dpi_spinners.append(spinner)
            grid.attach(spinner, 1, row, 1, 1)

            # Default radio button
            if i == 0:
                default_radio = Gtk.RadioButton()
            else:
                default_radio = Gtk.RadioButton.new_from_widget(self.default_radios[0])
            default_radio.connect("toggled", self._on_field_changed)
            default_radio.set_halign(Gtk.Align.CENTER)
            self.default_radios.append(default_radio)
            grid.attach(default_radio, 2, row, 1, 1)

            # Shift radio button
            if i == 0:
                shift_radio = Gtk.RadioButton()
            else:
                shift_radio = Gtk.RadioButton.new_from_widget(self.shift_radios[0])
            shift_radio.connect("toggled", self._on_field_changed)
            shift_radio.set_halign(Gtk.Align.CENTER)
            self.shift_radios.append(shift_radio)
            grid.attach(shift_radio, 3, row, 1, 1)

            row += 1

    def _populate_profile_list(self):
        """Populate the profile list from device.profiles"""
        self.profile_store.clear()

        if self.profiles and self.profiles.profiles:
            for profile_num, profile in sorted(self.profiles.profiles.items()):
                enabled_str = "✓" if profile.enabled else ""
                self.profile_store.append([profile_num, profile.name, enabled_str])

            # Select first profile by default
            self.profile_view.get_selection().select_path(0)

    def _on_profile_selected(self, selection):
        """Load selected profile into edit panel"""
        model, tree_iter = selection.get_selected()
        if tree_iter is None:
            return

        profile_num = model.get_value(tree_iter, 0)
        self.current_profile_num = profile_num
        profile = self.profiles.profiles[profile_num]

        # Disable change tracking while populating fields
        self._ignore_changes += 1

        try:
            # Set profile name
            self.name_entry.set_text(profile.name or "")

            # Set enabled switch
            self.enabled_switch.set_active(bool(profile.enabled))

            # Set DPI values
            for i in range(5):
                if i < len(profile.resolutions):
                    self.dpi_spinners[i].set_value(profile.resolutions[i])
                else:
                    self.dpi_spinners[i].set_value(800)

            # Set default DPI radio
            if 0 <= profile.resolution_default_index < 5:
                self.default_radios[profile.resolution_default_index].set_active(True)

            # Set shift DPI radio
            if 0 <= profile.resolution_shift_index < 5:
                self.shift_radios[profile.resolution_shift_index].set_active(True)

        finally:
            self._ignore_changes -= 1

    def _on_field_changed(self, *args):
        """Mark as modified when any field changes"""
        if self._ignore_changes == 0:
            self.modified = True
            self.save_button.set_sensitive(True)

    def _collect_profile_data(self):
        """Collect current values from edit fields"""
        if self.current_profile_num is None:
            return

        profile = self.profiles.profiles[self.current_profile_num]

        # Update profile name
        profile.name = self.name_entry.get_text()

        # Update enabled
        profile.enabled = 1 if self.enabled_switch.get_active() else 0

        # Update DPI values
        for i in range(5):
            profile.resolutions[i] = int(self.dpi_spinners[i].get_value())

        # Update default DPI index
        for i, radio in enumerate(self.default_radios):
            if radio.get_active():
                profile.resolution_default_index = i
                break

        # Update shift DPI index
        for i, radio in enumerate(self.shift_radios):
            if radio.get_active():
                profile.resolution_shift_index = i
                break

        # Update profile list display
        for row in self.profile_store:
            if row[0] == self.current_profile_num:
                enabled_str = "✓" if profile.enabled else ""
                row[1] = profile.name
                row[2] = enabled_str
                break

    def _on_save(self, *args):
        """Write profiles to device"""
        # Collect current field values
        self._collect_profile_data()

        # Write to device in async operation
        def _do_save():
            try:
                written = self.profiles.write(self.device)
                logger.info(f"Successfully wrote {written} sectors to device {self.device.name}")

                # Show success dialog on main thread
                common.ui_async(
                    lambda: self._show_message(
                        _("Success"),
                        _("Successfully updated profiles on %s.\nWrote %d sectors.") % (self.device.name, written),
                        Gtk.MessageType.INFO,
                    )
                )

                # Close dialog
                common.ui_async(lambda: self.dialog.destroy())

            except Exception as e:
                logger.error("Error writing profiles: %s", traceback.format_exc())
                common.ui_async(
                    lambda: self._show_message(
                        _("Error"), _("Failed to write profiles to device:\n%s") % str(e), Gtk.MessageType.ERROR
                    )
                )

        common.ui_async(_do_save)

    def _on_cancel(self, *args):
        """Handle cancel button"""
        if self.modified:
            # Show unsaved changes dialog
            dialog = Gtk.MessageDialog(
                parent=self.dialog,
                flags=Gtk.DialogFlags.MODAL,
                type=Gtk.MessageType.QUESTION,
                buttons=Gtk.ButtonsType.YES_NO,
                text=_("Discard unsaved changes?"),
            )
            dialog.format_secondary_text(_("You have unsaved changes. Are you sure you want to close without saving?"))
            response = dialog.run()
            dialog.destroy()

            if response != Gtk.ResponseType.YES:
                return

        self.dialog.destroy()

    def _on_delete(self, widget, event):
        """Handle window close button"""
        self._on_cancel()
        return True

    def _show_message(self, title, text, message_type):
        """Show a message dialog"""
        dialog = Gtk.MessageDialog(
            parent=self.dialog, flags=Gtk.DialogFlags.MODAL, type=message_type, buttons=Gtk.ButtonsType.OK, text=title
        )
        dialog.format_secondary_text(text)
        dialog.run()
        dialog.destroy()

    def show(self):
        """Show the dialog"""
        self.dialog.show_all()
