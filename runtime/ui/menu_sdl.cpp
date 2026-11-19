// SDL3 adapter of the in-game menu: the window's events to menu events (menu.h), as ui/menu_win.cpp does for Win32.
// Window thread (gfx_window_sdl.c's event loop, after input_sdl_event).
//
// F1 opens and closes the menu, Esc opens it (with the menu open, Esc goes to the menu, which closes). Esc also releases
// the cursor (input_sdl.c sees the event first; closing the menu gives the capture back). While the menu is open, its
// keys, the mouse and focus changes go to it; the game reads the keyboard through input_sdl.c and gets nothing while
// the menu is open (input_menu). Mouse positions come in window units and go to the menu in pixels.
#include <SDL3/SDL.h>

#include "imgui.h"

extern "C" {
#include "input.h"
#include "input_sdl.h"
#include "ui/menu.h"
}

static ImGuiKey key_of(SDL_Scancode sc) {
    switch (sc) {
    case SDL_SCANCODE_UP: return ImGuiKey_UpArrow;
    case SDL_SCANCODE_DOWN: return ImGuiKey_DownArrow;
    case SDL_SCANCODE_LEFT: return ImGuiKey_LeftArrow;
    case SDL_SCANCODE_RIGHT: return ImGuiKey_RightArrow;
    case SDL_SCANCODE_RETURN: case SDL_SCANCODE_KP_ENTER: return ImGuiKey_Enter;
    case SDL_SCANCODE_SPACE: return ImGuiKey_Space;
    case SDL_SCANCODE_ESCAPE: return ImGuiKey_Escape;
    case SDL_SCANCODE_TAB: return ImGuiKey_Tab;
    case SDL_SCANCODE_BACKSPACE: return ImGuiKey_Backspace;
    case SDL_SCANCODE_DELETE: return ImGuiKey_Delete;   // clears a cell of the remapping rows
    case SDL_SCANCODE_HOME: return ImGuiKey_Home;
    case SDL_SCANCODE_END: return ImGuiKey_End;
    case SDL_SCANCODE_PAGEUP: return ImGuiKey_PageUp;
    case SDL_SCANCODE_PAGEDOWN: return ImGuiKey_PageDown;
    case SDL_SCANCODE_LSHIFT: case SDL_SCANCODE_RSHIFT: return ImGuiKey_LeftShift;
    case SDL_SCANCODE_LCTRL: case SDL_SCANCODE_RCTRL: return ImGuiKey_LeftCtrl;
    case SDL_SCANCODE_Q: return ImGuiKey_Q;   // previous tab
    case SDL_SCANCODE_E: return ImGuiKey_E;   // next tab
    default: return ImGuiKey_None;
    }
}

extern "C" int menu_sdl_event(const SDL_Event *e) {
    static bool synthetic_owned;
    float d = (float)gfx_window_sdl_density();
    SDL_Window *window = gfx_window_sdl();
    SDL_WindowID own = window ? SDL_GetWindowID(window) : 0;
    switch (e->type) {
    case SDL_EVENT_FINGER_DOWN:
    case SDL_EVENT_FINGER_MOTION:
    case SDL_EVENT_FINGER_UP:
    case SDL_EVENT_FINGER_CANCELED: {
        if (!own || e->tfinger.windowID != own) return 0;
        int type = e->type == SDL_EVENT_FINGER_DOWN ? 0 : e->type == SDL_EVENT_FINGER_MOTION ? 1 :
                   e->type == SDL_EVENT_FINGER_UP ? 2 : 3;
        int consumed = menu_event_pointer(1,type,e->tfinger.touchID,e->tfinger.fingerID,e->tfinger.x,e->tfinger.y);
        if (type == 0) synthetic_owned = consumed != 0;
        return consumed;
    }
    case SDL_EVENT_KEY_DOWN:
        if (!menu_touch_enabled()) {
            if (!e->key.repeat && (e->key.scancode == SDL_SCANCODE_F1 ||
                (e->key.scancode == SDL_SCANCODE_ESCAPE && !menu_is_open()))) { menu_toggle(); return 0; }
            if (e->key.scancode == SDL_SCANCODE_F10) {
                if (!e->key.repeat) menu_perf_cycle();
                return 0;
            }
        }
        [[fallthrough]];
    case SDL_EVENT_KEY_UP:
        if (menu_is_open()) if (ImGuiKey k = key_of(e->key.scancode)) menu_event_key(k,e->type == SDL_EVENT_KEY_DOWN);
        return 0;
    case SDL_EVENT_MOUSE_MOTION:
        if (!own || e->motion.windowID != own) return 0;
        if (e->motion.which == SDL_TOUCH_MOUSEID && synthetic_owned) return 1;
        return menu_event_pointer(0,1,e->motion.which,0,e->motion.x*d,e->motion.y*d);
    case SDL_EVENT_MOUSE_BUTTON_DOWN:
    case SDL_EVENT_MOUSE_BUTTON_UP: {
        if (!own || e->button.windowID != own) return 0;
        if (e->button.which == SDL_TOUCH_MOUSEID && synthetic_owned) {
            if (e->type == SDL_EVENT_MOUSE_BUTTON_UP) synthetic_owned = false;
            return 1;
        }
        if (e->button.button == SDL_BUTTON_LEFT)
            return menu_event_pointer(0,e->type == SDL_EVENT_MOUSE_BUTTON_DOWN?0:2,e->button.which,0,e->button.x*d,e->button.y*d);
        if (menu_is_open()) {
            int b=e->button.button==SDL_BUTTON_RIGHT?1:e->button.button==SDL_BUTTON_MIDDLE?2:-1;
            if (b>=0) { menu_event_mouse_pos(e->button.x*d,e->button.y*d);menu_event_mouse_button(b,e->type==SDL_EVENT_MOUSE_BUTTON_DOWN); }
        }
        return 0;
    }
    case SDL_EVENT_MOUSE_WHEEL:
        if (menu_is_open()) menu_event_wheel(e->wheel.x,e->wheel.y);
        return 0;
    case SDL_EVENT_MOUSE_REMOVED:
        menu_event_mouse_removed(e->mdevice.which);return 0;
    case SDL_EVENT_WINDOW_FOCUS_GAINED:
    case SDL_EVENT_WINDOW_FOCUS_LOST:
        if (e->window.windowID == own) {
            if (e->type == SDL_EVENT_WINDOW_FOCUS_LOST) synthetic_owned = false;
            menu_event_focus(e->type == SDL_EVENT_WINDOW_FOCUS_GAINED);
        }
        return 0;
    case SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED:
    case SDL_EVENT_WINDOW_MINIMIZED:
        if (e->window.windowID == own) { synthetic_owned=false;menu_event_pointer_cancel(); }
        return 0;
    default: return 0;
    }
}
