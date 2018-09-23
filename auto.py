import os, sys
import subprocess, signal
import json
import threading, psutil
import time
from shutil import copy
import re
from subprocess import call
import datetime



def parseArg(arg):
    if arg[0:2] != "--":
        return True
    kwargs[arg[2:].split("=",2)[0]] = (arg[2:].split("=",2)[1] or "")
    return False

args = sys.argv[1:]
kwargs = {}
args = filter(parseArg, args)
foldername = args[0] if len(args) > 0 else os.path.splitext(os.path.basename(max([os.path.join("..\\..\\saves", basename) for basename in os.listdir("..\\..\\saves") if basename not in { "_autosave1.zip", "_autosave2.zip", "_autosave3.zip" }], key=os.path.getmtime)))[0]
savenames = args[1:] or foldername

possiblePaths = [
    "C:\\Program Files\\Factorio\\bin\\x64\\factorio.exe",
    "D:\\Program Files\\Factorio\\bin\\x64\\factorio.exe",
    "C:\\Games\\Factorio\\bin\\x64\\factorio.exe",
    "D:\\Games\\Factorio\\bin\\x64\\factorio.exe",
    "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Factorio\\bin\\x64\\factorio.exe",
    "D:\\Program Files (x86)\\Steam\\steamapps\\common\\Factorio\\bin\\x64\\factorio.exe"
]
try:
    factorioPath = kwargs["factorio"] if "factorio" in kwargs else next(x for x in possiblePaths if os.path.isfile(x))
except StopIteration:
    raise Exception("Can't find factorio.exe. Please pass the path as an argument.")

print(factorioPath)

psutil.Process(os.getpid()).nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS or 5)

basepath = kwargs["basepath"] if "basepath" in kwargs else "..\\..\\script-output\\FactorioMaps"
workthread = None
killthread = None


print("enabling FactorioMaps mod")
def changeModlist(newState):
    done = False
    with open("..\\mod-list.json", "r") as f:
        modlist = json.load(f)
    for mod in modlist["mods"]:
        if mod["name"] == "FactorioMaps":
            mod["enabled"] = newState
            done = True
    if not done:
        modlist["mods"].append({"name": "FactorioMaps", "enabled": newState})
    with open("..\\mod-list.json", "w") as f:
        json.dump(modlist, f, indent=2)

changeModlist(True)


try:
    for savename in savenames:
        workfolder = os.path.join(basepath, foldername)
        datapath = os.path.join(workfolder, "latest.txt")
        print(workfolder)



        print("cleaning up")
        if os.path.isfile(datapath):
            os.remove(datapath)



        if killthread and killthread.isAlive():
            print("waiting for previous factorio instance")
            killthread.join()

            print("updating mapInfo.json and mapInfo.js")
            with open(os.path.join(workfolder, "mapInfo.json"), 'r+') as outf, open(os.path.join(workfolder, "mapInfo.out.json"), "r") as inf:
                data = json.load(outf)
                data.update(json.load(inf))
                outf.seek(0)
                json.dump(data, outf)
                outf.truncate()



        print("creating autorun.lua from autorun.template.lua")
        if (os.path.isfile("autorun.lua")):
            if not os.path.isfile("autorun.lua.bak"):
                os.rename("autorun.lua", "autorun.lua.bak")

        if (os.path.isfile(os.path.join(workfolder, "mapInfo.json"))):
            with open(os.path.join(workfolder, "mapInfo.json"), "r") as f:
                mapInfoLua = re.sub(r'"([\d\w]+)" *:', lambda m: '["'+m.group(1)+'"] =' if m.group(1)[0].isdigit() else m.group(1)+' =', f.read().replace("[", "{").replace("]", "}"))
        else:
            mapInfoLua = "{}"
        if (os.path.isfile(os.path.join(workfolder, "chunkCache.json"))):
            with open(os.path.join(workfolder, "chunkCache.json"), "r") as f:
                chunkCache = re.sub(r'"([\d\w]+)" *:', lambda m: '["'+m.group(1)+'"] =' if m.group(1)[0].isdigit() else m.group(1)+' =', f.read().replace("[", "{").replace("]", "}"))
        else:
            chunkCache = "{}"

        with open("autorun.lua", "w") as target:
            with open("autorun.template.lua", "r") as template:
                for line in template:
                    target.write(line.replace("%%PATH%%", foldername + "/").replace("%%CHUNKCACHE%%", chunkCache.replace("\n", "\n\t")).replace("%%MAPINFO%%", mapInfoLua.replace("\n", "\n\t")).replace("%%DATE%%", datetime.date.today().strftime('%d/%m/%y')))


        print("starting factorio")
        p = subprocess.Popen(factorioPath + ' --load-game "' + savename + '"')

        if not os.path.exists(datapath):
            while not os.path.exists(datapath):
                time.sleep(1)

        latest = []
        with open(datapath, 'r') as f:
            for line in f:
                latest.append(line.rstrip("\n"))



        def watchAndKill():
            while not os.path.exists(os.path.join(os.path.join(basepath, latest[-1].split(" ")[0], "Images", *latest[-1].split(" ")[1:4]), "done.txt")):
                time.sleep(1)
            while not os.path.isfile(os.path.join(workfolder, "mapInfo2.json")):
                time.sleep(0.5)
                
            print("killing factorio")
            if p.poll() is None:
                p.kill()
            else:
                os.system("taskkill /im factorio.exe")
        
        killthread = threading.Thread(target=watchAndKill)
        killthread.daemon = True
        killthread.start()


        
        if workthread and workthread.isAlive():
            print("waiting for workthread")
            workthread.join()

        for screenshot in latest:
            print("Cropping %s images" % screenshot)
            if 0 != call('python crop.py %s %s' % (screenshot, basepath)): raise RuntimeError("crop failed")
            def refZoom():
                while not os.path.isfile(os.path.join(workfolder, "mapInfo2.json")):
                    time.sleep(0.5)
                if os.path.isfile(os.path.join(workfolder, "mapInfo.json")):
                    os.remove(os.path.join(workfolder, "mapInfo.json"))
                os.rename(os.path.join(workfolder, "mapInfo2.json"), os.path.join(workfolder, "mapInfo.json"))
                print("Crossreferencing %s images" % screenshot)
                if 0 != call('python ref.py %s %s' % (screenshot, basepath)): raise RuntimeError("ref failed")
                print("downsampling %s images" % screenshot)
                if 0 != call('python zoom.py %s %s' % (screenshot, basepath)): raise RuntimeError("zoom failed")
            if screenshot != latest[-1]:
                refZoom()
            else:
                workthread = threading.Thread(target=refZoom)
                workthread.daemon = True
                workthread.start()
        

        print("generating mapInfo.js")
        with open(os.path.join(workfolder, "mapInfo.js"), 'w+') as outf, open(os.path.join(workfolder, "mapInfo.json"), "r") as inf:
            outf.write("window.mapInfo = JSON.parse('")
            outf.write(inf.read())
            outf.write("');")



except KeyboardInterrupt:
    if not killthread or killthread.isAlive():
        print("killing factorio")
        if p.poll() is None:
            p.kill()
        else:
            os.system("taskkill /im factorio.exe")
    raise


if workthread.isAlive():
    print("waiting for workthread")
    workthread.join()
    

print("updating mapInfo.json and mapInfo.js")
with open(os.path.join(workfolder, "mapInfo.json"), 'r+') as outf, open(os.path.join(workfolder, "mapInfo.out.json"), "r") as inf:
    data = json.load(outf)
    for mapIndex, mapStuff in json.load(inf)["maps"].iteritems():
        for surfaceName, surfaceStuff in mapStuff["surfaces"].iteritems():
            data["maps"][int(mapIndex)]["surfaces"][surfaceName]["chunks"] = surfaceStuff["chunks"]
    outf.seek(0)
    json.dump(data, outf)
    outf.truncate()
os.remove(os.path.join(workfolder, "mapInfo.out.json"))


print("generating mapInfo.js")
with open(os.path.join(workfolder, "mapInfo.js"), 'w') as outf, open(os.path.join(workfolder, "mapInfo.json"), "r") as inf:
    outf.write("window.mapInfo = JSON.parse('")
    outf.write(inf.read())
    outf.write("');")



if killthread.isAlive():
    print("killing factorio")
    if p.poll() is None:
        p.kill()
    else:
        os.system("taskkill /im factorio.exe")
    
    
print("copying index.html")
#copy("index.html", os.path.join(workfolder, "index.html"))





print("enabling FactorioMaps mod")
changeModlist(False)



print("reverting autorun.lua")
if os.path.isfile("autorun.lua"):
    os.remove("autorun.lua")
os.rename("autorun.lua.bak", "autorun.lua")