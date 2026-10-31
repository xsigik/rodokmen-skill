#!/usr/bin/env python3
# Ověření čtení (např. po pomocníkovi): výřez zápisu rozdělený na dvě poloviny nejvýš 1900 px. Použití: overit.py <snímek.jpg> x0,y0,x1,y1 <prefix> [v] [--vylepsit]
# (v = dělit vodorovně; --vylepsit = vybledlý snímek: šedá, místní kontrast, doostření; potřebuje ImageMagick 7)
import glob,os,shutil,sys,subprocess
for _s in (sys.stdout, sys.stderr):   # UTF-8 výstup i na Windows bez -X utf8 (cp1250 neumí třeba „→“)
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")
def magick():  # když ImageMagick chybí, skončí hned (před stahováním) srozumitelnou hláškou
    m=shutil.which("magick") or next(iter(sorted(glob.glob(r"C:\Program Files\ImageMagick*\magick.exe"))),None) or (os.name!="nt" and shutil.which("convert"))  # IM6 bez magick; na Windows je convert.exe jiný program
    if not m: sys.exit("Chybí ImageMagick (příkaz magick). Nainstaluj ho (macOS: brew install imagemagick, Windows: winget install ImageMagick.ImageMagick a restart Claude Code / Codexu / OMP) a spusť nástroj znovu.")
    return m
MAGICK=magick()
VYLEPSIT=['-colorspace','Gray','-clahe','25x25%+128+4','-contrast-stretch','1%x50%','-level','5%,70%','-unsharp','0x1.2+1.2+0.02']
args=[a for a in sys.argv[1:] if a!='--vylepsit']; vylepsit='--vylepsit' in sys.argv
f,box,pre=args[:3]; mode=args[3] if len(args)>3 else 'h'
W,H=map(int,subprocess.run([MAGICK,f+'[0]','-format','%w %h','info:'],capture_output=True,text=True).stdout.split())
x0,y0,x1,y1=map(float,box.split(','))
if not (0<=x0<x1<=1 and 0<=y0<y1<=1): sys.exit(f'Oblast {box} musí být zlomky 0..1 (x0 < x1, y0 < y1), ne pixely.')
# překryv polovin 8 % oblasti (ne celé stránky – u úzkého výřezu by byl jinak větší než výřez)
if mode=='v': ym=(y0+y1)/2; p=0.08*(y1-y0); parts=[(x0,y0,x1,ym+p),(x0,ym-p,x1,y1)]
else: xm=(x0+x1)/2; p=0.08*(x1-x0); parts=[(x0,y0,xm+p,y1),(xm-p,y0,x1,y1)]
for i,(a,b,c,d) in enumerate(parts):
    o=f'{pre}_{i}.jpg'; subprocess.run([MAGICK,f,'-crop','%dx%d+%d+%d'%((c-a)*W,(d-b)*H,a*W,b*H),'+repage',*(VYLEPSIT if vylepsit else []),'-resize','1900x1900>',o]); print(o)
