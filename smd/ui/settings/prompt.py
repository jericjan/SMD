from enum import Enum

from prompt_toolkit import Application
from prompt_toolkit.data_structures import Point
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    FormattedTextControl,
    HSplit,
    Layout,
    ScrollbarMargin,
    VSplit,
    Window,
)
from prompt_toolkit.widgets import Frame

from smd.prompts import (
    prompt_confirm,
    prompt_dir,
    prompt_file,
    prompt_secret,
    prompt_select,
    prompt_text,
)
from smd.storage.settings import clear_setting, load_all_settings, set_setting
from smd.ui.settings.types import (
    SettingChangeCallback,
    SettingCustomTypes,
    SettingOperations,
    Settings,
)


class SettingsMenuPrompt:
    def __init__(
        self,
        ignore_list=None,
        on_setting_changed: SettingChangeCallback | None = None,
    ):
        self.ignore = ignore_list or []
        self.settings_list = [s for s in Settings if s not in self.ignore]
        self.current_index = 0
        self.cursor_offset = 0
        self.saved_settings = {}
        self.on_setting_changed = on_setting_changed

    def _setting_to_fmt_txt(self, setting: Settings, newline=True):
        """Takes a Setting and turns its value into formatted text"""
        val = self.saved_settings.get(setting.key_name)
        if val is None:
            val_str = "(unset)"
            val_style = "fg:ansigray"
        elif setting.hidden:
            val_str = "[ENCRYPTED]"
            val_style = "fg:ansiyellow"
        else:
            val_str = str(val)
            val_style = "fg:ansigreen"
        suffix = "\n" if newline else ""
        return (val_style, f"{val_str}{suffix}")

    def _get_menu_text(self):
        """Renders the left panel with setting names and values"""
        result = []
        for i, setting in enumerate(self.settings_list):
            is_selected = i == self.current_index
            pointer = "❯ " if is_selected else "  "

            val_style, val_str = self._setting_to_fmt_txt(setting)

            style = "fg:ansicyan bold" if is_selected else ""

            result.append((style, f"{pointer}{setting.clean_name}\n"))
            result.append((val_style, f"      {val_str}"))

        return result

    def _get_desc_text(self):
        """Renders the right panel with descriptions and other info."""
        if not self.settings_list:
            return [("", "No settings available.")]

        selected = self.settings_list[self.current_index]

        if isinstance(selected.type, type):
            type_str = selected.type.__name__
        elif isinstance(selected.type, list):
            type_str = "Enum List"
        else:
            type_str = selected.type.name

        val_style, val_str = self._setting_to_fmt_txt(selected)

        result = [
            ("fg:ansicyan bold", f"{selected.clean_name}\n"),
            (val_style, val_str),
            ("fg:ansigray", f"Key: {selected.key_name} | Type: {type_str}\n\n"),
        ]

        if isinstance(selected.description, str):
            result.append(("", selected.description))
        else:
            result.extend(selected.description)

        return result

    def _run_tui(self) -> tuple[Settings, SettingOperations] | None:
        """Builds and runs the TUI, returning the user's intent."""
        menu_control = FormattedTextControl(
            self._get_menu_text,
            focusable=True,
            show_cursor=False,
            get_cursor_position=lambda: Point(
                x=0, y=(self.current_index * 2) + self.cursor_offset
            ),
        )
        desc_control = FormattedTextControl(
            self._get_desc_text,
            show_cursor=False,
        )

        root_container = HSplit(
            [
                VSplit(
                    [
                        Frame(
                            Window(
                                content=menu_control,
                                width=60,
                                right_margins=[ScrollbarMargin(display_arrows=True)],
                            ),
                            title="Settings",
                        ),
                        Frame(
                            Window(
                                content=desc_control,
                                wrap_lines=True,
                                right_margins=[ScrollbarMargin(display_arrows=True)],
                            ),
                            title="Description",
                        ),
                    ],
                ),
                Frame(
                    Window(
                        FormattedTextControl(
                            "[↑/↓] Navigate  |  [Enter] Edit Value  |  [D] Delete Value  |  [Q/Esc] Quit"
                        ),
                        height=1,
                    )
                ),
            ]
        )

        kb = KeyBindings()

        @kb.add("up")
        @kb.add("k")
        def _(event):
            self.current_index = (self.current_index - 1) % len(self.settings_list)
            self.cursor_offset = (
                1 if self.current_index == len(self.settings_list) - 1 else 0
            )

        @kb.add("down")
        @kb.add("j")
        def _(event):
            self.current_index = (self.current_index + 1) % len(self.settings_list)
            self.cursor_offset = 0 if self.current_index == 0 else 1

        @kb.add("enter")
        def _(event):
            selected = self.settings_list[self.current_index]
            event.app.exit(result=(selected, SettingOperations.EDIT))

        @kb.add("d")
        @kb.add("delete")
        def _(event):
            selected = self.settings_list[self.current_index]
            event.app.exit(result=(selected, SettingOperations.DELETE))

        @kb.add("q")
        @kb.add("escape")
        def _(event):
            event.app.exit(result=None)

        app = Application(
            layout=Layout(root_container), key_bindings=kb, full_screen=True
        )

        return app.run()

    def execute(self):
        """Runs the Settings TUI, then handles the user's intent"""
        self.saved_settings = load_all_settings()
        while True:
            intent = self._run_tui()

            if intent is None:
                print("Exited settings.")
                break

            selected_key, operation = intent

            if operation == SettingOperations.DELETE:
                print(f"\nDeleting {selected_key.clean_name}...")
                clear_setting(selected_key)
                if selected_key.key_name in self.saved_settings:
                    del self.saved_settings[selected_key.key_name]
                continue

            if operation == SettingOperations.EDIT:
                print(f"\nEditing: {selected_key.clean_name}")
                new_settings_value = None

                try:
                    if selected_key.type == bool:
                        new_settings_value = prompt_confirm(
                            "Select the new value:", "Enable", "Disable"
                        )

                    elif isinstance(selected_key.type, list):
                        enum_val: Enum = prompt_select(
                            "Select the new value:", selected_key.type
                        )
                        new_settings_value = enum_val.value

                    elif selected_key.type == str:
                        func = prompt_secret if selected_key.hidden else prompt_text
                        new_settings_value = func("Enter the new value:")

                    elif selected_key.type == SettingCustomTypes.DIR:
                        new_settings_value = str(
                            prompt_dir("Enter the new directory:").resolve()
                        )

                    elif selected_key.type == SettingCustomTypes.FILE:
                        new_settings_value = str(
                            prompt_file("Enter the new file path:").resolve()
                        )

                    if new_settings_value is not None:
                        old_value = self.saved_settings.get(selected_key.key_name)
                        set_setting(selected_key, new_settings_value)
                        self.saved_settings[selected_key.key_name] = new_settings_value

                        if self.on_setting_changed:
                            self.on_setting_changed(
                                selected_key, old_value, new_settings_value
                            )

                except KeyboardInterrupt:
                    continue
