"""Exercise production touch routing, SDL events, menu buttons, config and real ImGui frames."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
IMGUI = ROOT / 'runtime/third_party/imgui'


@unittest.skipUnless(sys.platform == 'linux', 'Linux/Deck touch integration')
class TouchMenu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='touch-menu-', dir=Path.cwd())
        cls.addClassCleanup(cls.temp.cleanup)
        cls.folder = Path(cls.temp.name)
        cls.objects = []
        for name in ('imgui', 'imgui_draw', 'imgui_tables', 'imgui_widgets'):
            out = cls.folder / (name + '.o')
            subprocess.run(['g++', '-std=c++17', '-O0', '-g0', '-fsanitize=address,undefined',
                            '-I'+str(IMGUI), '-c', str(IMGUI/(name+'.cpp')), '-o', str(out)],
                           check=True, timeout=100)
            cls.objects.append(str(out))

    def run_source(self, text, *, c=False, sdl=False, imgui=False):
        name = self._testMethodName
        source = self.folder / (name + ('.c' if c else '.cpp'))
        binary = self.folder / name
        source.write_text(text)
        command = ['cc' if c else 'g++', '-std=gnu17' if c else '-std=c++17', '-O1', '-g0',
                   '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                   '-I'+str(ROOT/'runtime'), '-I'+str(IMGUI)]
        deps = Path(os.environ['NATIVE_DEPS'])
        command += ['-I'+str(deps/'include'), str(source)]
        if imgui:
            command += self.objects
        if sdl:
            command += ['-L'+str(deps/'lib'), '-Wl,-rpath,'+str(deps/'lib'), '-lSDL3']
        command += ['-pthread', '-lm', '-o', str(binary)]
        subprocess.run(command, check=True, timeout=70)
        subprocess.run([str(binary)], cwd=self.folder, check=True, timeout=20)

    def test_production_queue_owns_one_pointer_cancels_and_retains_world_release(self):
        text = (ROOT/'runtime/ui/menu.cpp').read_text()
        core = text[text.index('// ---- open state, any thread'):text.index('// ---- gamepad navigation:')]
        self.run_source(r'''
#include <atomic>
#include <mutex>
#include <cassert>
#include <cstring>
#include <cstdint>
#include "imgui.h"
#include "ui/native_touch.h"
using PlatMutex=std::mutex;
#define PLAT_MUTEX_INIT {}
static void plat_mutex_lock(PlatMutex *p){p->lock();}
static void plat_mutex_unlock(PlatMutex *p){p->unlock();}
static int blocked;
static void input_menu(int open){blocked=open?1:2;}
static void rt_log(const char *,...){}
static int touch_on=1;
static const char *cfg_value(const char *){return touch_on?"auto":"0";}
static const char *cfg_device_profile(){return "deck";}
extern "C" int menu_is_open(void);
extern "C" void menu_event_pointer_cancel(void);
''' + core + r'''
static int g_failed_flag(){return 0;}
static void reset(){
 menu_event_pointer_cancel();set_open(0);g_reset=0;
 pointer_width=1280;pointer_height=800;hit_left=1200;hit_top=720;hit_right=1270;hit_bottom=790;
}
int main(){
 reset();assert(menu_event_pointer(1,0,7,8,.96f,.95f)==1 && blocked==1 && g_pointer_capture==1);
 int n=ev_n;assert(menu_event_pointer(1,0,7,9,.1f,.1f)==1 && ev_n==n);
 assert(menu_event_pointer(0,0,42,0,1230,760)==1 && ev_n==n);
 assert(menu_event_pointer(1,2,7,9,.1f,.1f)==1 && g_pointer_capture==1);
 assert(menu_event_pointer(1,2,7,8,.96f,.95f)==1 && g_pointer_capture==0 && blocked==2);
 reset();assert(!menu_event_pointer(0,0,42,0,10,10));set_open(1);
 assert(!menu_event_pointer(0,2,42,0,1230,760) && !pointer.mouse.outside);
 reset();menu_event_pointer(1,0,7,8,.96f,.95f);menu_event_pointer(1,3,7,8,.96f,.95f);
 assert(g_pointer_capture==0 && g_reset==1 && ev_n==0);
 reset();menu_event_pointer(0,0,42,0,1230,760);menu_event_mouse_removed(99);assert(g_pointer_capture==1);
 menu_event_mouse_removed(42);assert(g_pointer_capture==0 && g_reset==1);
 reset();menu_event_pointer(1,0,7,8,.96f,.95f);menu_event_focus(0);
 assert(g_pointer_capture==0 && pointer_width==0 && g_reset==1);
 reset();menu_event_pointer(1,0,7,8,.96f,.95f);
 for(int i=0;i<EV_MAX+2;i++)push({EV_KEY,i,1,0,0});
 assert(g_reset==1 && g_pointer_capture==0 && !nd_pointer_active(&pointer));
 reset();menu_event_pointer(0,0,42,0,1230,760);
 assert(menu_event_pointer(0,1,42,0,10,10)==1 && g_pointer_capture==1);
 assert(menu_event_pointer(0,2,42,0,10,10)==1 && g_pointer_capture==0);
 reset();menu_event_pointer(1,0,7,8,.96f,.95f);touch_on=0;
 assert(menu_event_pointer(1,1,7,8,.96f,.95f)==0 && g_pointer_capture==0 && g_reset==1);
 touch_on=1;
 return 0;
}
''', imgui=True)

    def test_real_sdl_adapter_touch_synthetic_mouse_window_and_shortcut_rules(self):
        self.run_source(r'''
#include <cassert>
#include <cstdlib>
#include "ui/menu_sdl.cpp"
static SDL_Window *window;
static int is_open, touch=1, accept=1, pointers, toggles, perfs, cancels, keys;
extern "C" SDL_Window *gfx_window_sdl(){return window;}
extern "C" double gfx_window_sdl_density(){return 2;}
extern "C" int menu_is_open(){return is_open;}
extern "C" int menu_touch_enabled(){return touch;}
extern "C" void menu_toggle(){toggles++;}
extern "C" void menu_perf_cycle(){perfs++;}
extern "C" int menu_event_pointer(int k,int t,uint64_t,uint64_t,float x,float y){
 pointers++;if(k){assert(x==.9f && y==.8f);}else{assert(x==20 && y==40);}return accept;
}
extern "C" void menu_event_pointer_cancel(){cancels++;}
extern "C" void menu_event_mouse_removed(uint64_t){cancels++;}
extern "C" void menu_event_key(int,int){keys++;}
extern "C" void menu_event_mouse_pos(float,float){}
extern "C" void menu_event_mouse_button(int,int){}
extern "C" void menu_event_wheel(float,float){}
extern "C" void menu_event_focus(int){}
int main(){
 setenv("SDL_VIDEODRIVER","dummy",1);assert(SDL_Init(SDL_INIT_VIDEO));
 window=SDL_CreateWindow("private hidden adapter test",1280,800,SDL_WINDOW_HIDDEN);assert(window);
 SDL_Event e={};e.type=SDL_EVENT_FINGER_DOWN;e.tfinger.windowID=SDL_GetWindowID(window);
 e.tfinger.x=.9f;e.tfinger.y=.8f;assert(menu_sdl_event(&e)==1 && pointers==1);
 e.tfinger.windowID++;assert(menu_sdl_event(&e)==0 && pointers==1);e.tfinger.windowID--;
 e.type=SDL_EVENT_FINGER_UP;assert(menu_sdl_event(&e)==1 && pointers==2);
 e={};e.type=SDL_EVENT_MOUSE_BUTTON_DOWN;e.button.windowID=SDL_GetWindowID(window);
 e.button.which=SDL_TOUCH_MOUSEID;e.button.button=SDL_BUTTON_LEFT;e.button.x=10;e.button.y=20;
 assert(menu_sdl_event(&e)==1 && pointers==2);e.type=SDL_EVENT_MOUSE_BUTTON_UP;
 assert(menu_sdl_event(&e)==1 && pointers==2);
 e.type=SDL_EVENT_MOUSE_BUTTON_DOWN;e.button.which=4;assert(menu_sdl_event(&e)==1 && pointers==3);
 e={};e.type=SDL_EVENT_KEY_DOWN;e.key.scancode=SDL_SCANCODE_F1;menu_sdl_event(&e);
 e.key.scancode=SDL_SCANCODE_F10;menu_sdl_event(&e);assert(!toggles && !perfs);
 touch=0;e.key.scancode=SDL_SCANCODE_F1;menu_sdl_event(&e);
 e.key.scancode=SDL_SCANCODE_F10;menu_sdl_event(&e);assert(toggles==1 && perfs==1);
 e={};e.type=SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED;e.window.windowID=SDL_GetWindowID(window);
 menu_sdl_event(&e);assert(cancels==1);
 SDL_DestroyWindow(window);SDL_Quit();return 0;
}
''', sdl=True)

    def test_menu_physical_a_b_is_independent_of_world_binding(self):
        text = (ROOT/'runtime/input.c').read_text()
        sample = text[text.index('int input_pad_read('):text.index('uint16_t rumble_motor(')]
        self.run_source(r'''
#include <assert.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>
#include <SDL3/SDL.h>
enum{B_A,B_B,B_X};
static int state=1,deck=1,south,east;
static int lock;
static SDL_Gamepad *pad;
static void plat_mutex_lock(int *p){(void)p;}
static void plat_mutex_unlock(int *p){(void)p;}
static void start(void){}
static void binds_refresh(void){}
static const char *cfg_device_profile(void){return deck?"deck":"desktop";}
static int pad_read(uint64_t *b,int32_t *l,int32_t *r){*b=7;l[0]=123;l[1]=-456;r[0]=r[1]=0;return 1;}
static bool unit_button(SDL_Gamepad *p,SDL_GamepadButton b){(void)p;return b==SDL_GAMEPAD_BUTTON_SOUTH?south:east;}
#define SDL_GetGamepadButton unit_button
''' + sample + r'''
int main(){
 uint64_t b;int32_t x,y;
 for(int s=0;s<2;s++)for(int e=0;e<2;e++){
  south=s;east=e;assert(input_pad_read(&b,&x,&y));assert(b==(4u|(unsigned)s|((unsigned)e<<1)));
  assert(x==123 && y==-456);
 }
 deck=0;assert(input_pad_read(&b,&x,&y) && b==7);
 state=-1;assert(!input_pad_read(&b,&x,&y) && !b);return 0;
}
''', c=True)

    def test_production_config_persists_dock_live_choices_and_preserves_other_keys(self):
        cfg = (ROOT/'runtime/cfg.c').read_text().replace('#include "host.h"', '').replace(
            '#include "platform/platform.h"', '')
        self.run_source(r'''
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <pthread.h>
#include "cfg.h"
typedef pthread_mutex_t PlatMutex;
#define PLAT_MUTEX_INIT PTHREAD_MUTEX_INITIALIZER
static void plat_mutex_lock(PlatMutex *p){assert(!pthread_mutex_lock(p));}
static void plat_mutex_unlock(PlatMutex *p){assert(!pthread_mutex_unlock(p));}
static void rt_log(const char *fmt,...){(void)fmt;}
static _Noreturn void rt_fatal(const char *fmt,...){(void)fmt;abort();}
static uint8_t *plat_file_read(const char *p,uint64_t *size){
 FILE *f=fopen(p,"rb");if(!f)return NULL;assert(!fseek(f,0,SEEK_END));long n=ftell(f);assert(n>=0);rewind(f);
 uint8_t *b=calloc((size_t)n+1,1);assert(b && fread(b,1,(size_t)n,f)==(size_t)n);fclose(f);*size=(uint64_t)n;return b;
}
static bool plat_file_exists(const char *p){struct stat s;return !stat(p,&s);}
static uint64_t plat_file_size(const char *p){struct stat s;assert(!stat(p,&s));return s.st_size;}
static bool plat_file_write_atomic(const char *p,const void *b,uint64_t n){
 char temp[256];assert(snprintf(temp,sizeof temp,"%s.tmp",p)>0);FILE *f=fopen(temp,"wb");assert(f);
 assert(fwrite(b,1,n,f)==n && !fclose(f));return !rename(temp,p);
}
static bool plat_exe_path(char *p,size_t n){(void)p;(void)n;return false;}
#define plat_last_sep(p) strrchr((p),'/')
''' + cfg + r'''
static const char *retained_old_value;
int main(){
 setenv("AC_DEVICE_PROFILE","desktop",1);
 FILE *f=fopen("settings.ini","wb");assert(f);
 const char *initial="# preserve this comment\n[input]\nrumble_strength = 77\n[menu]\ntouch_ui = auto\ntouch_dock = 4\n";
 assert(fwrite(initial,1,strlen(initial),f)==strlen(initial) && !fclose(f));
 assert(cfg_load("settings.ini"));
 assert(!strcmp(cfg_meta("TOUCH_UI")->def,"auto") && !strcmp(cfg_meta("TOUCH_DOCK")->def,"4"));
 retained_old_value=cfg_get("AC_TOUCH_DOCK");
 cfg_set("AC_TOUCH_DOCK","0");cfg_set("AC_FPS","30");cfg_set("AC_MOTION","0");cfg_set("AC_PERF_OVERLAY","fps");
 assert(!strcmp(retained_old_value,"4") && cfg_save_to("settings.ini"));
 uint64_t n;uint8_t *saved=plat_file_read("settings.ini",&n);
 assert(strstr((char*)saved,"# preserve this comment\n") && strstr((char*)saved,"rumble_strength = 77\n"));
 free(saved);assert(cfg_load("settings.ini"));
 assert(cfg_int("AC_TOUCH_DOCK")==0 && cfg_int("AC_FPS")==30 && !cfg_bool("AC_MOTION"));
 assert(!strcmp(cfg_value("AC_PERF_OVERLAY"),"fps") && cfg_int("AC_RUMBLE_STRENGTH")==77);
 setenv("AC_TOUCH_DOCK","7",1);assert(cfg_from_env("AC_TOUCH_DOCK") && cfg_int("AC_TOUCH_DOCK")==7);
 unsetenv("AC_TOUCH_DOCK");assert(cfg_int("AC_TOUCH_DOCK")==0);return 0;
}
''', c=True)

    def test_real_imgui_badge_quick_request_drag_docks_and_bounds(self):
        self.run_source(r'''
#include <cassert>
#include <cstring>
#include "ui/touch_chrome.h"
#include "imgui_internal.h"
extern "C" const char *menu_text(UiTextId id){
 switch(id){case UI_MENU_TOUCH_HIDE:return "Hide";case UI_MENU_TOUCH_QUICK:return "Quick panel";
 case UI_MENU_TOUCH_SETTINGS:return "All settings";case UI_MENU_TOUCH_HINT:return "Drag to dock";
 case UI_MENU_FPS_LIMIT:return "Frame rate";case UI_MENU_MOTION:return "Motion";
 case UI_MENU_PERF_OVERLAY:return "Performance overlay";case UI_MENU_ON:return "On";case UI_MENU_OFF:return "Off";
 case UI_MENU_PERF_OFF:return "Off";case UI_MENU_PERF_FPS:return "FPS";case UI_MENU_PERF_FULL:return "Full";
 case UI_MENU_TAB_SCREEN:return "Screen";case UI_MENU_TAB_CONTROLS:return "Controls";case UI_MENU_TAB_CHEATS:return "Cheats";
 default:return "Other";}
}
static TouchChrome s;
static TouchChoices v={60,1,0,false,false,false,false};
static TouchRequest frame(int layer,int dock,float x=-100,float y=-100,int down=-1){
 auto &io=ImGui::GetIO();io.AddMousePosEvent(x,y);if(down>=0)io.AddMouseButtonEvent(0,down!=0);
 ImGui::NewFrame();TouchRequest r=touch_chrome_draw(s,layer,dock,v);ImGui::Render();return r;
}
int main(){
 ImGui::CreateContext();auto &io=ImGui::GetIO();io.IniFilename=nullptr;io.DisplaySize=ImVec2(1280,800);io.DeltaTime=1.f/60;
 unsigned char *pixels;int w,h;io.Fonts->GetTexDataAsRGBA32(&pixels,&w,&h);
 for(int dock=0;dock<8;dock++)for(int layer=0;layer<2;layer++){
  frame(layer,dock);assert(s.lower.x>=0 && s.lower.y>=0 && s.upper.x<=1280 && s.upper.y<=800);
  assert(ImGui::GetDrawData()->TotalVtxCount>0);
 }
 frame(0,4);float x=(s.lower.x+s.upper.x)*.5f,y=(s.lower.y+s.upper.y)*.5f;
 frame(0,4,x,y,1);auto r=frame(0,4,x,y,0);assert(r.layer==1);
 frame(1,4);ImGuiWindow *window=ImGui::FindWindowByName("##touch-chrome");assert(window);
 // Real button activation requests a live setting; it does not change config from the drawing helper.
 float bx=s.lower.x+100,by=s.lower.y+205;
 frame(1,4,bx,by,1);r=frame(1,4,bx,by,0);
 assert(r.fps==30 && r.motion==-1 && r.perf==-1);
 ImGuiID nav=ImGui::GetCurrentContext()->NavId;assert(nav);
 v.fps=30;frame(1,4,bx,by);
 assert(ImGui::GetCurrentContext()->NavId==nav && ImGui::GetCurrentContext()->NavIdIsAlive);
 frame(1,4,bx,by,1);r=frame(1,4,bx,by,0);assert(r.fps==60);
 v.fps=60;v.fps_locked=true;
 frame(1,4,bx,by,1);r=frame(1,4,bx,by,0);assert(r.fps==-1);
 v.fps_locked=false;
 frame(1,4,bx,s.lower.y+263,1);r=frame(1,4,bx,s.lower.y+263,0);
 assert(r.motion==0 && r.fps==-1 && r.perf==-1);
 frame(1,4,bx,s.lower.y+321,1);r=frame(1,4,bx,s.lower.y+321,0);
 assert(r.perf==1 && r.fps==-1 && r.motion==-1);
 frame(1,4,bx,s.lower.y+387,1);r=frame(1,4,bx,s.lower.y+387,0);
 assert(r.layer==2 && r.page==0);
 frame(1,4,bx,s.lower.y+85,1);r=frame(1,4,bx,s.lower.y+85,0);assert(r.layer==0);
 frame(0,4);x=(s.lower.x+s.upper.x)*.5f;y=(s.lower.y+s.upper.y)*.5f;
 frame(0,4,x,y,1);frame(0,4,15,15);frame(0,4,15,15);
 r=frame(0,4,15,15,0);assert(r.dock==0 && r.layer==-1);
 for(ImVec2 size:{ImVec2(800,600),ImVec2(320,240),ImVec2(24,24)}){
  io.DisplaySize=size;frame(0,0);assert(s.lower.x>=0 && s.lower.y>=0 && s.upper.x<=size.x && s.upper.y<=size.y);
 }
 ImGui::DestroyContext();return 0;
}
''', imgui=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
