"""Cross-platform desktop computer control with optional screen understanding."""
from __future__ import annotations
import asyncio, os, platform, shutil, subprocess
from typing import Any

def _pyautogui():
    try: import pyautogui
    except ImportError as exc: raise RuntimeError("GUI control requires pyautogui") from exc
    pyautogui.PAUSE = 0.05
    return pyautogui

def _screenshot_path(path):
    if path: return os.path.abspath(os.path.expanduser(path))
    root=os.path.join(os.getcwd(), ".kemi", "screenshots"); os.makedirs(root, exist_ok=True)
    import time
    return os.path.join(root, f"screen-{int(time.time()*1000)}.png")

async def screen_capture(path=None):
    target=_screenshot_path(path); os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    image=await asyncio.to_thread(_pyautogui().screenshot); await asyncio.to_thread(image.save,target)
    return {"path":target,"width":image.width,"height":image.height,"ok":True}

async def screen_size():
    s=await asyncio.to_thread(_pyautogui().size); return {"width":int(s.width),"height":int(s.height)}
async def mouse_position():
    p=await asyncio.to_thread(_pyautogui().position); return {"x":int(p.x),"y":int(p.y),"ok":True}
async def mouse_move(x,y,duration=.15):
    await asyncio.to_thread(_pyautogui().moveTo,int(x),int(y),max(0.,float(duration))); return {"x":int(x),"y":int(y),"ok":True}
async def mouse_click(x=None,y=None,button="left",clicks=1):
    button=str(button).lower()
    if button not in {"left","middle","right"}: return {"error":"button must be left, middle, or right"}
    kw={"clicks":max(1,int(clicks)),"button":button}
    if x is not None and y is not None: kw.update(x=int(x),y=int(y))
    await asyncio.to_thread(_pyautogui().click,**kw); return {"x":x,"y":y,"button":button,"clicks":kw["clicks"],"ok":True}
async def mouse_drag(x,y,duration=.3,button="left"):
    button=str(button).lower()
    if button not in {"left","middle","right"}: return {"error":"button must be left, middle, or right"}
    await asyncio.to_thread(_pyautogui().dragTo,int(x),int(y),max(0.,float(duration)),button=button); return {"x":int(x),"y":int(y),"button":button,"ok":True}
async def mouse_scroll(clicks,x=None,y=None):
    p=_pyautogui()
    if x is not None and y is not None: await asyncio.to_thread(p.moveTo,int(x),int(y),0)
    await asyncio.to_thread(p.scroll,int(clicks)); return {"clicks":int(clicks),"x":x,"y":y,"ok":True}

async def clipboard_set(text):
    try:
        import pyperclip; await asyncio.to_thread(pyperclip.copy,str(text)); return {"characters":len(str(text)),"ok":True}
    except Exception as exc: return {"error":f"clipboard unavailable: {exc}"}
async def clipboard_get():
    try:
        import pyperclip; text=await asyncio.to_thread(pyperclip.paste); return {"text":str(text),"characters":len(str(text)),"ok":True}
    except Exception as exc: return {"error":f"clipboard unavailable: {exc}"}
async def keyboard_type(text,interval=.01):
    text=str(text)
    try:
        p=_pyautogui()
        if text.isascii(): await asyncio.to_thread(p.write,text,interval=max(0.,float(interval))); return {"characters":len(text),"mode":"direct","ok":True}
        import pyperclip; await asyncio.to_thread(pyperclip.copy,text); await asyncio.to_thread(p.hotkey,"command" if platform.system()=="Darwin" else "ctrl","v")
        return {"characters":len(text),"mode":"clipboard-paste","ok":True}
    except Exception as exc: return {"error":f"keyboard input failed: {exc}"}
async def keyboard_press(key):
    await asyncio.to_thread(_pyautogui().press,str(key)); return {"key":str(key),"ok":True}
async def keyboard_hotkey(keys):
    if not keys: return {"error":"keys must not be empty"}
    await asyncio.to_thread(_pyautogui().hotkey,*[str(k) for k in keys]); return {"keys":[str(k) for k in keys],"ok":True}

async def ocr_screen(path=None,language="eng"):
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc: return {"error":f"OCR requires pytesseract and Pillow: {exc}"}
    try:
        image=Image.open(os.path.abspath(os.path.expanduser(path))) if path else await asyncio.to_thread(_pyautogui().screenshot)
        data=await asyncio.to_thread(pytesseract.image_to_data,image,lang=str(language),output_type=pytesseract.Output.DICT)
        items=[]; parts=[]
        for i,raw in enumerate(data.get("text",[])):
            text=str(raw).strip()
            if not text: continue
            try: conf=float(data["conf"][i])
            except (ValueError,TypeError,KeyError): conf=-1.
            item={"text":text,"confidence":conf,"x":int(data["left"][i]),"y":int(data["top"][i]),"width":int(data["width"][i]),"height":int(data["height"][i])}
            items.append(item); parts.append(text)
        return {"text":" ".join(parts)[:12000],"items":items[:500],"count":len(items),"ok":True}
    except Exception as exc: return {"error":f"OCR failed: {exc}"}

async def find_text(text,language="eng",min_confidence=30.):
    query=str(text).strip().casefold()
    if not query: return {"error":"text is required"}
    result=await ocr_screen(language=language)
    if result.get("error"): return result
    matches=[i for i in result.get("items",[]) if i.get("confidence",-1)>=float(min_confidence) and query in i.get("text","").casefold()]
    if not matches: return {"found":False,"query":text,"ok":True}
    best=max(matches,key=lambda i:i.get("confidence",0)); return {"found":True,"query":text,"x":best["x"]+best["width"]//2,"y":best["y"]+best["height"]//2,"match":best,"matches":matches[:20],"ok":True}
async def click_text(text,language="eng",min_confidence=30.,button="left"):
    found=await find_text(text,language,min_confidence)
    if not found.get("found"): return found
    click=await mouse_click(found["x"],found["y"],button=button); return {**found,"click":click,"ok":bool(click.get("ok"))}

async def launch_app(command,args=None):
    command=str(command).strip()
    if not command: return {"error":"command is required"}
    argv=[command]+[str(x) for x in (args or [])]
    try:
        kw={"creationflags":getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)} if platform.system()=="Windows" else {"start_new_session":True}
        proc=await asyncio.to_thread(subprocess.Popen,argv,**kw); return {"pid":proc.pid,"command":argv,"ok":True}
    except FileNotFoundError: return {"error":f"application not found: {command}"}
    except Exception as exc: return {"error":str(exc)}

async def active_window():
    system=platform.system()
    try:
        if system=="Windows":
            import pygetwindow as gw; win=await asyncio.to_thread(gw.getActiveWindow); return {"title":getattr(win,"title","") if win else "","ok":True}
        if system=="Darwin": proc=await asyncio.create_subprocess_exec("osascript","-e",'tell application "System Events" to get name of first application process whose frontmost is true',stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        else:
            if not shutil.which("xdotool"): return {"title":"","supported":False,"note":"install xdotool for active-window metadata","ok":True}
            proc=await asyncio.create_subprocess_exec("xdotool","getactivewindow","getwindowname",stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        stdout,stderr=await asyncio.wait_for(proc.communicate(),timeout=5)
        return {"title":stdout.decode(errors="replace").strip(),"ok":proc.returncode==0,"error":stderr.decode(errors="replace")[:500] if proc.returncode else None}
    except ImportError: return {"supported":False,"note":"install pygetwindow for Windows window metadata","ok":True}
    except Exception as exc: return {"error":str(exc)}

async def list_windows():
    system=platform.system()
    try:
        if system=="Windows":
            import pygetwindow as gw; ws=await asyncio.to_thread(gw.getAllWindows); return {"windows":[{"title":getattr(w,"title",""),"x":getattr(w,"left",None),"y":getattr(w,"top",None),"width":getattr(w,"width",None),"height":getattr(w,"height",None)} for w in ws if getattr(w,"title","")],"ok":True}
        if system=="Linux" and shutil.which("wmctrl"):
            proc=await asyncio.create_subprocess_exec("wmctrl","-lG",stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE); out,err=await proc.communicate()
            if proc.returncode: return {"error":err.decode(errors="replace")[:500]}
            ws=[]
            for line in out.decode(errors="replace").splitlines():
                p=line.split(None,6)
                if len(p)>=7:
                    try: ws.append({"id":p[0],"x":int(p[2]),"y":int(p[3]),"width":int(p[4]),"height":int(p[5]),"title":p[6]})
                    except ValueError: pass
            return {"windows":ws,"ok":True}
        return {"windows":[],"supported":False,"ok":True}
    except Exception as exc: return {"error":str(exc)}

async def window_action(action,title=""):
    system=platform.system(); action=str(action).lower()
    if action not in {"focus","minimize","maximize","restore","close"}: return {"error":"invalid window action"}
    try:
        if system=="Windows":
            import pygetwindow as gw; matches=await asyncio.to_thread(gw.getWindowsWithTitle,title)
            if not matches: return {"error":f"window not found: {title}"}
            win=matches[0]; await asyncio.to_thread(getattr(win,{"focus":"activate","minimize":"minimize","maximize":"maximize","restore":"restore","close":"close"}[action])); return {"title":getattr(win,"title",title),"action":action,"ok":True}
        if system=="Linux" and shutil.which("wmctrl"):
            cmd={"focus":["wmctrl","-a",title],"close":["wmctrl","-c",title],"minimize":["wmctrl","-r",title,"-b","add,hidden"],"maximize":["wmctrl","-r",title,"-b","add,maximized_vert,maximized_horz"],"restore":["wmctrl","-r",title,"-b","remove,hidden"]}[action]
            proc=await asyncio.create_subprocess_exec(*cmd,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE); out,err=await proc.communicate(); return {"action":action,"stdout":out.decode(errors="replace"),"error":err.decode(errors="replace") or None,"ok":proc.returncode==0}
        return {"supported":False,"action":action,"ok":True}
    except ImportError: return {"supported":False,"note":"install pygetwindow for Windows window control","ok":True}
    except Exception as exc: return {"error":str(exc)}
