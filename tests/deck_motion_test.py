"""Native Deck sensor decoding, descriptor ownership and production-loop arbitration."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(sys.platform == 'linux', 'Linux native IMU backend')
class DeckMotion(unittest.TestCase):
    def run_c(self, text, decoder=True):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as folder:
            source, binary = Path(folder)/'motion.c', Path(folder)/'motion'
            source.write_text(text)
            command = ['cc', '-std=gnu17', '-O1', '-g', '-fsanitize=address,undefined',
                       '-fno-sanitize-recover=all', '-I'+str(ROOT/'runtime'), str(source)]
            if decoder:
                command.append(str(ROOT/'runtime/deck_motion_decode.c'))
            subprocess.run([*command, '-lm', '-o', str(binary)], check=True, timeout=40)
            subprocess.run([str(binary)], check=True, timeout=10)

    def test_decoder_matches_existing_sdl_rotation_and_ignores_buttons(self):
        code = (ROOT/'runtime/input.c').read_text()
        axes = code[code.index('void input_motion_axes('):code.index('// Under lock: (re)enable')]
        self.run_c(r'''
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <string.h>
#include "deck_motion.h"
#define SDL_STANDARD_GRAVITY 9.80665f
''' + axes + r'''
static void put16(unsigned char *p,int v) {p[0]=(unsigned)v;p[1]=(unsigned)v>>8;}
int main(void) {
 unsigned char p[65]={1,0,9,64},q[65];uint32_t packet;double a[3],g[3],sa[3],sg[3];
 const int raw[3]={-32768,12345,16384};
 for(int i=0;i<3;i++) {put16(p+24+2*i,raw[i]);put16(p+30+2*i,raw[i]);}
 p[4]=0xff;p[5]=0xff;p[6]=0xff;p[7]=0xff;
 assert(nd_deck_motion_decode(p,64,&packet,a,g) && packet==UINT32_MAX);
 float sdl_a[3]={raw[0]*2.f/32768*SDL_STANDARD_GRAVITY,raw[2]*2.f/32768*SDL_STANDARD_GRAVITY,-raw[1]*2.f/32768*SDL_STANDARD_GRAVITY};
 const float scale=2000.f/32768*(3.14159265358979323846f/180.f);
 float sdl_g[3]={raw[0]*scale,raw[2]*scale,-raw[1]*scale};input_motion_axes(sdl_a,sdl_g,sa,sg);
 for(int i=0;i<3;i++) {assert(fabs(a[i]-sa[i])<1e-5);assert(fabs(g[i]-sg[i])<1e-5);}
 assert(a[0]==2.0 && a[2]==-1.0);
 memcpy(q,p,65);memset(q+8,0xab,16);double qa[3],qg[3];
 assert(nd_deck_motion_decode(q,64,&packet,qa,qg) && !memcmp(a,qa,sizeof a) && !memcmp(g,qg,sizeof g));
 assert(!nd_deck_motion_decode(p,63,&packet,a,g));assert(!nd_deck_motion_decode(p,65,&packet,a,g));
 assert(!nd_deck_motion_decode(NULL,64,&packet,a,g));p[2]=8;assert(!nd_deck_motion_decode(p,64,&packet,a,g));
 p[2]=9;memset(p+24,0,6);assert(!nd_deck_motion_decode(p,64,&packet,a,g));return 0;
}
''')

    def test_real_message_fds_identity_freshness_backoff_and_cleanup(self):
        self.run_c(r'''
#define _GNU_SOURCE
#include <assert.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/hidraw.h>
#include <linux/input.h>
#include <poll.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <unistd.h>
#include "deck_motion.h"
static int channels[3][2],kind[1024],owned[1024],live,dirpos,opens,scans,deny,many,interrupt_poll;
static DIR *test_opendir(const char *p) {assert(!strcmp(p,"/dev"));dirpos=0;scans++;return (DIR *)(uintptr_t)1;}
static struct dirent *test_readdir(DIR *d) {
 assert(d==(DIR *)(uintptr_t)1);static struct dirent e;
 if(dirpos >= (many?40:4))return NULL;
 if(!many && dirpos==3)strcpy(e.d_name,"hidraw3evil");else snprintf(e.d_name,sizeof e.d_name,"hidraw%d",dirpos);
 dirpos++;return &e;
}
static int test_closedir(DIR *d) {assert(d==(DIR *)(uintptr_t)1);return 0;}
static int test_open(const char *p,int flags,...) {
 assert((flags&O_ACCMODE)==O_RDONLY && (flags&O_NONBLOCK) && (flags&O_CLOEXEC) && (flags&O_NOFOLLOW));
 opens++;if(deny) {errno=EACCES;return -1;}
 int k=-1;assert(sscanf(p,"/dev/hidraw%d",&k)==1 && k>=0 && k<3);
 int fd=fcntl(channels[k][0],F_DUPFD_CLOEXEC,3);assert(fd>=0 && fd<1024);kind[fd]=k;owned[fd]=1;live++;return fd;
}
static int test_fstat(int fd,struct stat *s) {assert(owned[fd]);memset(s,0,sizeof *s);s->st_mode=S_IFCHR|0600;return 0;}
static int test_ioctl(int fd,unsigned long req,...) {
 assert(owned[fd] && req==HIDIOCGRAWINFO);va_list args;va_start(args,req);struct hidraw_devinfo *p=va_arg(args,void *);va_end(args);
 *p=(struct hidraw_devinfo){.bustype=BUS_USB,.vendor=kind[fd]?0x28de:0x1234,.product=0x1205};return 0;
}
static int test_close(int fd) {assert(owned[fd]);owned[fd]=0;live--;return close(fd);}
static int test_poll(struct pollfd *p,nfds_t n,int timeout) {
 assert(timeout==0);if(interrupt_poll){interrupt_poll=0;errno=EINTR;return -1;}return poll(p,n,timeout);
}
#define opendir test_opendir
#define readdir test_readdir
#define closedir test_closedir
#define open test_open
#define fstat test_fstat
#define ioctl test_ioctl
#define close test_close
#define poll test_poll
#include "deck_motion_linux.c"
#undef opendir
#undef readdir
#undef closedir
#undef open
#undef fstat
#undef ioctl
#undef close
#undef poll
static void report(unsigned char *p,uint32_t packet,int sample) {
 memset(p,0,65);p[0]=1;p[2]=9;p[3]=64;
 for(int i=0;i<4;i++)p[4+i]=(unsigned char)(packet>>(8*i));
 p[28]=0;p[29]=0x40;p[30]=(unsigned)sample;p[31]=(unsigned)sample>>8;
}
static void send_report(int k,const unsigned char *p,size_t n) {assert(write(channels[k][1],p,n)==(ssize_t)n);}
int main(void) {
 for(int i=0;i<3;i++)assert(!socketpair(AF_UNIX,SOCK_SEQPACKET|SOCK_NONBLOCK|SOCK_CLOEXEC,0,channels[i]));
 DeckImu s=DECK_IMU_INIT;double a[3],g[3];unsigned char p[65];uint64_t t=1000000000;
 assert(nd_deck_imu_read(&s,t,a,g)==-1 && live==2 && scans==1 && opens==3);
 report(p,1,1);p[2]=8;send_report(1,p,64);report(p,UINT32_MAX,100);send_report(2,p,64);
 assert(nd_deck_imu_read(&s,t+1,a,g)==1 && s.packet==UINT32_MAX && live==1 && a[2]==-1);
 int selected=s.fds[0];assert(fcntl(selected,F_GETFD)&FD_CLOEXEC);
 send_report(2,p,64);assert(nd_deck_imu_read(&s,t+2,a,g)==0 && s.sample_ns==t+1);
 report(p,0,200);send_report(2,p,64);assert(nd_deck_imu_read(&s,t+3,a,g)==1 && !s.packet);
 report(p,1,32767);send_report(2,p,64);report(p,0,-32768);send_report(2,p,64);
 assert(nd_deck_imu_read(&s,t+4,a,g)==1 && s.packet==1 && g[0]>0);
 report(p,2,2);send_report(2,p,65);assert(nd_deck_imu_read(&s,t+5,a,g)==0 && s.sample_ns==t+4);
 interrupt_poll=1;assert(nd_deck_imu_read(&s,t+6,a,g)==0 && live==1);
 assert(nd_deck_imu_read(&s,t+4+IMU_STALE_NS,a,g)==-1 && !live);
 errno=0;assert(fcntl(selected,F_GETFD)==-1 && errno==EBADF);
 int previous=scans;assert(nd_deck_imu_read(&s,s.retry_ns-1,a,g)==-1 && scans==previous);
 t=s.retry_ns;assert(nd_deck_imu_read(&s,t,a,g)==-1 && live==2);
 report(p,3,1);send_report(2,p,64);assert(nd_deck_imu_read(&s,t+1,a,g)==1 && live==1);
 close(channels[2][1]);channels[2][1]=-1;
 assert(nd_deck_imu_read(&s,t+2,a,g)==-1 && !live);
 nd_deck_imu_close(&s);nd_deck_imu_close(&s);assert(!live);
 deny=1;many=1;opens=0;t+=2000000000;assert(nd_deck_imu_read(&s,t,a,g)==-1 && opens==32 && !live);
 for(int i=0;i<3;i++){close(channels[i][0]);if(channels[i][1]>=0)close(channels[i][1]);}
 puts("Native Deck IMU: real message fds, opened-device identity, wrap/duplicate/stale reports, bounded discovery, HUP and exact closure PASS");
 return 0;
}
''')

    def test_existing_motion_loop_arbitrates_native_sdl_disable_and_disconnect(self):
        text = (ROOT/'runtime/input.c').read_text()
        loop = text[text.index('static void motion_main('):text.index('void input_motion_start(')]
        self.run_c(r'''
#include <assert.h>
#include <setjmp.h>
#include <stdint.h>
#include <stdio.h>
#include "deck_motion.h"
static jmp_buf done;
static int tick,lock,pad_value,*pad=&pad_value,connected=1,enabled=1,feeds,restarts,closes;
static void plat_wait_ns(uint64_t n) {assert(n==4000000);if(++tick==7)longjmp(done,1);connected=tick!=5;enabled=tick!=4;}
static void plat_mutex_lock(int *l) {assert(!*l);*l=1;}
static void plat_mutex_unlock(int *l) {assert(*l);*l=0;}
static int SDL_GamepadConnected(int *p) {(void)p;return connected;}
static void SDL_UpdateGamepads(void) {assert(lock);}
static int sensors_ready(void) {assert(lock);return tick==1;}
static unsigned SDL_GetGamepadVendor(int *p) {(void)p;return 0x054c;}
static unsigned SDL_GetGamepadProduct(int *p) {(void)p;return 0x0ce6;}
#define SDL_SENSOR_ACCEL 1
#define SDL_SENSOR_GYRO 2
static int SDL_GetGamepadSensorData(int *p,int sensor,float *v,int n) {(void)p;(void)sensor;assert(lock && n==3);v[0]=1;v[1]=2;v[2]=3;return 1;}
static int input_motion_enabled(void) {return enabled;}
static uint64_t kern_now_ns(void) {return (uint64_t)tick*4000000;}
static void *motion_global(void) {return &tick;}
static void motion_restart(void *m) {assert(m==&tick && !lock);restarts++;}
static void input_motion_axes(const float *a,const float *g,double *aa,double *gg) {(void)a;(void)g;assert(!lock);aa[0]=11;gg[0]=12;}
void nd_deck_imu_close(DeckImu *s) {(void)s;assert(!lock);closes++;}
int nd_deck_imu_read(DeckImu *s,uint64_t now,double *a,double *g) {
 (void)s;assert(!lock && now==kern_now_ns() && connected && enabled && tick!=1);
 if(tick==2){a[0]=21;g[0]=22;return 1;}return tick==3?0:-1;
}
static void motion_feed(void *m,const double *a,const double *g,uint64_t now) {
 assert(m==&tick && !lock && now==kern_now_ns());feeds++;
 if(tick==1)assert(a[0]==11 && g[0]==12);else {assert(tick==2 && a[0]==21 && g[0]==22);}
}
''' + loop + r'''
int main(void) {if(!setjmp(done))motion_main(NULL);assert(feeds==2 && restarts==2 && closes==3 && !lock);return 0;}
''', decoder=False)


if __name__ == '__main__':
    unittest.main()
