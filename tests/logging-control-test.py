#!/usr/bin/env python3
from pathlib import Path
import subprocess,struct,os,json,time,hashlib,tempfile
root=Path(__file__).resolve().parents[1]
temporary=tempfile.TemporaryDirectory(prefix='yarp-logging-test-')
tests=Path(temporary.name)
b=root/'overlays/device/sony/pdx234/bootlog'
(tests/'policy_cli.c').write_text(r'''
#include "logging_settings.h"
int main(int argc, char** argv) {
 if (argc != 2) return 2;
 FILE* f=fopen(argv[1], "rb");
 if (!f) return 2;
 int value=yarp_logging_from_settings(f); fclose(f);
 printf("%d\n",value);return 0;
}
''')
subprocess.run(['gcc','-std=gnu11','-Wall','-Wextra','-Werror','-I'+str(b),str(tests/'policy_cli.c'),'-o',str(tests/'policy_cli')],check=True)
def fixture(values,version=0x10010):
 result=struct.pack('<I',version)
 for k,v in values:
  for s in (k,v):
   p=s.encode()+b'\0';result+=struct.pack('<H',len(p))+p
 return result
for name,data,wanted in [
 ('older',fixture([('tw_language','zh_CN')]),1),
 ('on',fixture([('tw_metadata_logging','1')]),1),
 ('off',fixture([('tw_metadata_logging','0')]),0),
 ('off-last',fixture([('tw_metadata_logging','1'),('tw_metadata_logging','0')]),0),
 ('invalid',fixture([('tw_metadata_logging','x')]),-1),
 ('wrong-version',fixture([('tw_metadata_logging','0')],1234),-1),
 ('truncated',fixture([('tw_metadata_logging','0')])[:-1],-1),
 ('tail-corrupt',fixture([('tw_metadata_logging','0')])+b'\x02',-1),
 ('embedded-key',fixture([('tw_metadata_logging\0extra','0')]),1)]:
 p=tests/(name+'.settings');p.write_bytes(data)
 got=int(subprocess.check_output([str(tests/'policy_cli'),str(p)],text=True))
 assert got==wanted,(name,got,wanted)
print('PASS: early boot policy parser, default-on migration, on/off, invalid and truncated files.')
testroot=tests/'runtime';testroot.mkdir(exist_ok=True)
(testroot/'metadata').mkdir(exist_ok=True)
(testroot/'persist/TWRP').mkdir(parents=True,exist_ok=True)
# Keep production logger logic intact; only redirect paths and filesystem IDs
# to a fixture instead of probing or mounting any real host block device.
s=(b/'yarp_bootlog.c').read_text()
s=s.replace('"/metadata"','"'+str(testroot/'metadata')+'"')
s=s.replace('"/mnt/vendor/persist"','"'+str(testroot/'persist')+'"')
s=s.replace('"/mnt/vendor"','"'+str(testroot)+'"')
(tests/'test_logger.c').write_text(s)
(tests/'logging_settings.h').write_bytes((b/'logging_settings.h').read_bytes())
include=tests/'include/sys';include.mkdir(parents=True,exist_ok=True)
(include/'system_properties.h').write_text(r'''
#ifndef TEST_SYSTEM_PROPERTIES_H
#define TEST_SYSTEM_PROPERTIES_H
#include <stdint.h>
#define PROP_VALUE_MAX 92
typedef struct prop_info { int unused; } prop_info;
int __system_property_get(const char*,char*);
int __system_property_set(const char*,const char*);
int __system_property_foreach(void (*)(const prop_info*,void*),void*);
void __system_property_read_callback(const prop_info*,void (*)(void*,const char*,const char*,uint32_t),void*);
#endif
''')
hooks=r'''
#define _GNU_SOURCE 1
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/statfs.h>
#include <sys/system_properties.h>
int __system_property_get(const char* name,char* value) {
 const char* p = !strcmp(name,"twrp.yarp.logging") ? "@ROOT@/policy" : "@ROOT@/active";
 FILE* f=fopen(p,"rb"); if(!f) { value[0]=0;return 0; }
 size_t n=fread(value,1,1,f);value[n]=0;fclose(f);return (int)n;
}
int __system_property_set(const char* name,const char* value) {
 if(strcmp(name,"twrp.yarp.logging_active")) return -1;
 FILE* f=fopen("@ROOT@/active","wb");if(!f)return -1;
 fputs(value,f);return fclose(f);
}
int __system_property_foreach(void (*cb)(const prop_info*,void*),void* v) { (void)cb;(void)v;return 0; }
void __system_property_read_callback(const prop_info* p,void (*cb)(void*,const char*,const char*,uint32_t),void* v) { (void)p;(void)cb;(void)v; }
static int test_stat(const char* p,struct stat* s) {
 int rc=stat(p,s);
 if(!rc && (!strcmp(p,"@ROOT@/metadata") || !strcmp(p,"@ROOT@/persist")))s->st_dev=(dev_t)987654321;
 return rc;
}
static int test_statfs(const char* p,struct statfs* s) {
 int rc=statfs(p,s);if(!rc && !strcmp(p,"@ROOT@/metadata"))s->f_type=0xef53;return rc;
}
#define stat(path,result) test_stat(path,result)
#define statfs(path,result) test_statfs(path,result)
'''
(tests/'hooks.h').write_text(hooks.replace('@ROOT@',str(testroot)))
subprocess.run(['gcc','-std=gnu11','-Wall','-Wextra','-Werror','-D__ANDROID__','-I'+str(tests/'include'),'-include',str(tests/'hooks.h'),str(tests/'test_logger.c'),'-o',str(tests/'test_logger')],check=True)
def fingerprint():
 result={}
 for p in (testroot/'metadata').rglob('*'):
  st=p.stat();result[str(p.relative_to(testroot))]=(st.st_mtime_ns,st.st_size,hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None)
 return result
def waitfor(fn,secs=5):
 end=time.monotonic()+secs
 while time.monotonic()<end:
  if fn():return
  time.sleep(.05)
 raise AssertionError('runtime logger condition timed out')
def active():return (testroot/'active').read_text() if (testroot/'active').exists() else ''
def start():return subprocess.Popen([str(tests/'test_logger')],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
settings=testroot/'persist/TWRP/.twrp_settings'
settings.write_bytes(fixture([('tw_metadata_logging','0')]))
before=fingerprint();process=start()
try:
 time.sleep(1.2);assert process.poll() is None
 assert fingerprint()==before,'persisted off boot touched Metadata'
 process.terminate();process.wait(timeout=3)
 assert fingerprint()==before,'disabled shutdown wrote logs'
finally:
 if process.poll() is None:process.kill();process.wait()
print('PASS: saved off prevents all Metadata writes on boot and shutdown.')
settings.unlink();process=start()
try:
 status=testroot/'metadata/XQ-DQ72-YARP/logs/latest/status.txt'
 waitfor(lambda:status.exists());assert active()=='1'
 (testroot/'policy').write_text('0')
 waitfor(lambda:active()=='0')
 paused=fingerprint();time.sleep(1.2)
 assert fingerprint()==paused,'runtime off continues Metadata writes'
 (testroot/'policy').write_text('1')
 waitfor(lambda:active()=='1')
 waitfor(lambda:fingerprint()!=paused)
 assert not (testroot/'metadata/XQ-DQ72-YARP/logs/previous').exists(),'re-enable rotated the current boot'
 (testroot/'policy').write_text('0');waitfor(lambda:active()=='0')
 paused=fingerprint();process.terminate();process.wait(timeout=3)
 assert fingerprint()==paused,'stop took a forbidden final snapshot'
finally:
 if process.poll() is None:process.kill();process.wait()
print('PASS: default on, immediate pause acknowledgement, no paused writes, resume without rotation, no final snapshot.')
(testroot/'policy').unlink()
settings.write_bytes(fixture([('tw_metadata_logging','0')]))
before=fingerprint();process=start()
try:
 time.sleep(1.2);assert fingerprint()==before
 process.terminate();process.wait(timeout=3);assert fingerprint()==before
finally:
 if process.poll() is None:process.kill();process.wait()
print('PASS: remembered off preserves existing metadata logs unchanged on the next boot.')
(tests/'result.log').write_text('PASS early policy parser; saved off zero metadata writes; live off/on; no shutdown snapshot; remembered off reboot\n')

temporary.cleanup()
