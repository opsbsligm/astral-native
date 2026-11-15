/* SPDX-License-Identifier: MIT */
/* Present-thread touch chrome. Requests reuse the existing config and menu pages. */
#pragma once
#include "imgui.h"
#include <algorithm>
#include <cmath>
#include <cstdio>
extern "C" {
#include "ui_text.h"
}

struct TouchChrome {
    ImVec2 position, start, lower, upper;
    int previous_layer = -1, previous_dock = -1;
    bool dragging = false, moved = false;
};
struct TouchChoices { int fps, motion, perf; bool fps_locked, motion_locked, perf_locked, dock_locked, save_failed; };
struct TouchRequest { int layer = -1, page = -1, dock = -1, fps = -1, motion = -1, perf = -1; };
static const ImVec2 touch_docks[] = {{0,0},{.5f,0},{1,0},{1,.5f},{1,1},{.5f,1},{0,1},{0,.5f}};

static inline void touch_drag(TouchChrome &s, float scale) {
    if (ImGui::IsItemActivated()) { s.start = s.position; s.moved = false; }
    if (ImGui::IsItemActive() && ImGui::IsMouseDragging(0, 8 * scale)) {
        s.dragging = s.moved = true;
        ImVec2 d = ImGui::GetMouseDragDelta();
        s.position = ImVec2(s.start.x + d.x, s.start.y + d.y);
    }
}

// layer 0 is the badge, 1 is the quick panel. The complete menu keeps its existing pages.
static inline TouchRequest touch_chrome_draw(TouchChrome &s, int layer, int dock, const TouchChoices &v) {
    TouchRequest r;
    ImVec2 screen = ImGui::GetIO().DisplaySize;
    float k = std::clamp(screen.y / 800.f, .75f, 1.35f), gap = 12 * k;
    dock = std::clamp(dock, 0, 7);
    ImVec2 size = layer ? ImVec2(std::min(368 * k, screen.x - 2 * gap), std::min(600 * k, screen.y - 2 * gap))
                       : ImVec2(std::max(48.f, 56 * k), std::max(48.f, 56 * k));
    size.x = std::clamp(size.x, 1.f, std::max(1.f, screen.x));
    size.y = std::clamp(size.y, 1.f, std::max(1.f, screen.y));
    if (!s.dragging || s.previous_layer != layer || s.previous_dock != dock) {
        s.position = ImVec2(gap + touch_docks[dock].x * (screen.x - 2 * gap - size.x),
                            gap + touch_docks[dock].y * (screen.y - 2 * gap - size.y));
    }
    s.previous_layer = layer; s.previous_dock = dock;
    s.position.x = std::clamp(s.position.x, 0.f, std::max(0.f, screen.x - size.x));
    s.position.y = std::clamp(s.position.y, 0.f, std::max(0.f, screen.y - size.y));
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(18 * k, 14 * k));
    ImGui::PushStyleVar(ImGuiStyleVar_WindowRounding, 18 * k);
    ImGui::PushStyleVar(ImGuiStyleVar_FrameRounding, 10 * k);
    ImGui::PushStyleVar(ImGuiStyleVar_FramePadding, ImVec2(12 * k, 12 * k));
    ImGui::PushStyleVar(ImGuiStyleVar_ItemSpacing, ImVec2(10 * k, 10 * k));
    ImGui::PushStyleVar(ImGuiStyleVar_WindowMinSize, ImVec2(1,1));
    ImGui::PushStyleColor(ImGuiCol_WindowBg, ImVec4(.035f, .065f, .09f, .98f));
    ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(.09f, .17f, .22f, 1));
    ImGui::PushStyleColor(ImGuiCol_ButtonHovered, ImVec4(.15f, .31f, .36f, 1));
    ImGui::PushStyleColor(ImGuiCol_ButtonActive, ImVec4(.22f, .42f, .46f, 1));
    ImGui::SetNextWindowPos(s.position, ImGuiCond_Always);
    ImGui::SetNextWindowSize(size, ImGuiCond_Always);
    ImGui::Begin("##touch-chrome", nullptr, ImGuiWindowFlags_NoTitleBar | ImGuiWindowFlags_NoResize |
        ImGuiWindowFlags_NoCollapse | ImGuiWindowFlags_NoMove | ImGuiWindowFlags_NoSavedSettings |
        (layer ? 0 : ImGuiWindowFlags_NoScrollbar));
    s.lower = ImGui::GetWindowPos(); ImVec2 actual = ImGui::GetWindowSize();
    s.upper = ImVec2(s.lower.x + actual.x, s.lower.y + actual.y);
    const float row = std::max(48.f, 48 * k);
    if (!layer) {
        ImGui::SetCursorPos(ImVec2(0,0));
        bool clicked = ImGui::InvisibleButton("##touch-badge", size);
        if (!v.dock_locked) touch_drag(s, k);
        if (clicked && !s.moved) r.layer = 1;
        ImVec2 c(s.lower.x + size.x * .5f, s.lower.y + size.y * .5f);
        ImDrawList *draw = ImGui::GetWindowDrawList();
        draw->AddRect(s.lower, s.upper, IM_COL32(112,217,198,220), 18*k, 0, 1.4f*k);
        for (int i = -1; i <= 1; i++) {
            float y = c.y + i * 8 * k, x = c.x + (i == 0 ? 4 : -4) * k;
            draw->AddLine(ImVec2(c.x-13*k,y), ImVec2(c.x+13*k,y), IM_COL32(214,240,235,255), 2*k);
            draw->AddCircleFilled(ImVec2(x,y), 3.5f*k, IM_COL32(112,217,198,255));
        }
    } else {
        ImGui::TextDisabled("%s", menu_text(UI_MENU_TOUCH_QUICK));
        ImGui::TextUnformatted("ASTRAL CHAIN");
        if (ImGui::Button(menu_text(UI_MENU_TOUCH_HIDE), ImVec2(-1, row))) r.layer = 0;
        ImGui::InvisibleButton("##touch-dock-handle", ImVec2(-1, row));
        ImVec2 p = ImGui::GetItemRectMin(), q = ImGui::GetItemRectMax();
        ImGui::GetWindowDrawList()->AddRectFilled(ImVec2(p.x+(q.x-p.x)*.35f,p.y+18*k),
            ImVec2(p.x+(q.x-p.x)*.65f,p.y+23*k), IM_COL32(112,217,198,200), 3*k);
        if (!v.dock_locked) touch_drag(s, k);
        auto choice = [&](UiTextId label, const char *value, bool locked) {
            ImGui::BeginDisabled(locked);
            ImGui::PushID((int)label);
            char text[256]; snprintf(text, sizeof text, "%s: %s###live-choice", menu_text(label), value);
            bool selected = ImGui::Button(text, ImVec2(-1, row));
            ImGui::PopID(); ImGui::EndDisabled(); return selected;
        };
        if (choice(UI_MENU_FPS_LIMIT, v.fps == 30 ? "30" : "60", v.fps_locked)) r.fps = v.fps == 30 ? 60 : 30;
        if (choice(UI_MENU_MOTION, menu_text(v.motion ? UI_MENU_ON : UI_MENU_OFF), v.motion_locked)) r.motion = !v.motion;
        const UiTextId perf[] = {UI_MENU_PERF_OFF, UI_MENU_PERF_FPS, UI_MENU_PERF_FULL};
        if (choice(UI_MENU_PERF_OVERLAY, menu_text(perf[std::clamp(v.perf,0,2)]), v.perf_locked)) r.perf = (v.perf + 1) % 3;
        ImGui::Separator();
        const UiTextId names[] = {UI_MENU_TAB_SCREEN, UI_MENU_TAB_CONTROLS, UI_MENU_TAB_CHEATS, UI_MENU_TOUCH_SETTINGS};
        float width = (ImGui::GetContentRegionAvail().x - ImGui::GetStyle().ItemSpacing.x) * .5f;
        for (int i = 0; i < 4; i++) {
            if (i % 2) ImGui::SameLine();
            ImGui::PushID(i);
            char text[128]; snprintf(text,sizeof text,"%s###full-page",menu_text(names[i]));
            if (ImGui::Button(text, ImVec2(width, std::max(52.f, 52*k)))) { r.layer = 2; r.page = i; }
            ImGui::PopID();
        }
        if (v.save_failed) ImGui::TextColored(ImVec4(1,.55f,.4f,1),"%s",menu_text(UI_MENU_SAVE_FAILED));
        else ImGui::TextWrapped("%s", menu_text(v.dock_locked?UI_MENU_SET_BY_ENV:UI_MENU_TOUCH_HINT));
        if (ImGui::IsKeyPressed(ImGuiKey_GamepadFaceRight, false) || ImGui::IsKeyPressed(ImGuiKey_Escape, false)) r.layer = 0;
    }
    if (s.dragging && !ImGui::IsMouseDown(0)) {
        s.dragging = false;
        if (s.moved) {
            float best = 1e30f;
            for (int i = 0; i < 8; i++) {
                float dx = (s.position.x + size.x*.5f) / std::max(1.f,screen.x) - touch_docks[i].x;
                float dy = (s.position.y + size.y*.5f) / std::max(1.f,screen.y) - touch_docks[i].y;
                if (dx*dx+dy*dy < best) { best = dx*dx+dy*dy; r.dock = i; }
            }
            r.layer = -1; // a drag never becomes an opening tap
        }
        s.moved = false;
    }
    ImGui::End(); ImGui::PopStyleColor(4); ImGui::PopStyleVar(6);
    return r;
}
