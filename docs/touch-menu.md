# Deck touch menu

`AC_TOUCH_UI=auto` enables the corner badge for the existing Deck device profile and retains the desktop menu otherwise. `0` disables it and `1` enables it explicitly. The Menu page exposes this setting. In touch mode F1, Esc and the controller opening chords do not open the application menu; Esc and physical B can still dismiss an open menu. The existing gameplay bindings and other setting defaults are unchanged.

Tap the badge for the quick panel. Its live frame-rate, motion and performance-overlay controls use the existing config consumers, environment locks and delayed save path. Screen, Controls, Cheats and All settings open the existing complete menu. Its Back button returns to the quick panel and Hide collapses it. The panel reports a settings-save failure. New labels use the existing English/Simplified Chinese catalog and font collection.

Drag the badge or panel handle to any of the eight edge/corner docks. `AC_TOUCH_DOCK=0..7` is saved through `cfg_set` and `cfg_save`, with default 4 (bottom right). Environment overrides also lock docking. The drawing helper only returns requests; it never writes settings or accesses game state.

The SDL window adapter routes native finger events and ordinary mouse input before gameplay input. One pointer owns its complete gesture; secondary fingers and synthetic mouse duplicates cannot click a second control. A press begun in the world retains its release even when a menu opens meanwhile. Focus loss, resize, device removal and queue overflow cancel a gesture without activating its last item. Events cross the existing bounded queue; ImGui and Vulkan remain on the presentation thread.

Only application-menu sampling uses physical Deck south=A and east=B independently of gameplay rebinding. This does not yet adapt the original game's menus, prompts or QTEs. The quick panel exposes the existing 30/60 frame-rate choices; it does not claim a new performance tier, upscaler or game capability.

`tests/touch_menu_test.py` exercises production queue/routing code, the actual SDL adapter, the menu-only button sample, config persistence and real ImGui frames under ASan/UBSan. These component checks and the runtime build do not establish touchscreen usability, Chinese glyph availability, Vulkan output, game-menu behavior or long-session stability on the actual Deck. Those remain open; `hardware_validated=false`.
