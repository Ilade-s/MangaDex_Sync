"""
Script to use if you want to convert between the 2 file systems (in one way or another) :
    - {vol}/{chap}/{page}.* : easier to browse, harder to read
    - {vol}/{chap}-{page}.* : easier to read, harder to browse
    - automatically remove old system and pass existant files if already in place
"""

import os # IO (mkdir/makedirs, remove)
import json # json handling
from rich import print # pretty print 
from rich.progress import * # progress bar

print("============================================")
print("[bold red]WARNING : this converter uses search.json to convert ALL search results from a file system from another :[/bold red]")
print("Incomplete archives can be used but [bold red]aren't recommended[/bold red] (can cause problems)")
print("============================================")
# confirmation of the mangas to convert
with open("search.json", "r", encoding="UTF-8") as file:
    dataSearch = json.load(file)
    titlelist = ["".join(list(filter(lambda x: x not in (".", ":", ",", "?") , m["data"]["attributes"]["title"]["en"]))) 
            for m in dataSearch["results"]]
confirm = input(f"Mangas to convert : {titlelist} \n\tIs this correct (y or n) ? ")
if confirm != "y":
    print("[bold red]Conversion cancelled[/bold red]")
    exit()
# search of file system
print("============================================")
print("File systems :")
print("\t- 0 : [bold red]vol/chap/page.*[/bold red] : \n\t\teasier to browse but harder to read chapters")
print("\t- 1 : [bold red]vol/chap-page.*[/bold red] : \n\t\teasier to read chapters but harder to browse")
print("============================================")
pathAll = os.path.join(titlelist[0], "chapters")
currentFS = ("vol/chap-page.*" if [file for file in os.listdir(os.path.join(pathAll, os.listdir(pathAll)[0])) 
                                    if os.path.isfile(os.path.join(pathAll, os.listdir(pathAll)[0], file))] 
        else "vol/chap/page.*") # check if there is files in volumes folders to know the file system
print(f"Current file system : [bold green]{currentFS}[/bold green]")
fsChoice = (1 if currentFS == "vol/chap/page.*" else 0)
confirm = input(f"\tFile system to convert to : {fsChoice} \n\tIs this correct (y or n) ? ")
if confirm != "y":
    print("[bold red]Conversion cancelled[/bold red]")
    exit()
# search of the file quality
if fsChoice:
    pathVol = os.path.join(pathAll, os.listdir(pathAll)[0])
    pathChap = os.path.join(pathVol, os.listdir(pathVol)[0])
    quality = (1 if os.path.join(pathChap, os.listdir(pathChap)[0])[-3:] == "png" else 0)
else:
    quality = (1 if os.listdir(os.path.join(pathAll, os.listdir(pathAll)[0]))[0][-3:] == "png" else 0)
fileFormat = ("png" if quality else "jpg")
confirm = input(f"File format : {fileFormat} \n\tIs this correct (y or n) ? ")
if confirm != "y":
    print("[bold red]Conversion cancelled[/bold red]")
    exit()
# for each manga
for m in dataSearch["results"]:
    idManga = m["data"]["id"]
    name = "".join(list(filter(lambda x: x not in (".", ":", ",", "?") , m["data"]["attributes"]["title"]["en"])))

    with open(f"{name}/chapters.json", "r", encoding="UTF-8") as file:
        chapters = json.load(file)
        # sort the list from the json to make loading of images in order
        chapters.sort(key=lambda c: (float(c["data"]["attributes"]["chapter"]) 
                                    if c["data"]["attributes"]["chapter"] != None 
                                    else 0))

    print("[italic]Replacing images...[/italic]")
    baseServer = ""
    previousChap = ""
    # for each chapter
    i = 0
    # create progress bar for chapters 
    prgbar = Progress()
    prgbar.start()
    for c in chapters:
        # chapter infos
        vol = c["data"]["attributes"]["volume"]
        chap = c["data"]["attributes"]["chapter"]
        id = c["data"]["id"]
        imgPaths = c["data"]["attributes"]["dataSaver"]
        hash = c["data"]["attributes"]["hash"]
        try:
            title = "".join(list(filter(lambda x: x not in (".", ":", '"', "?"), c["data"]["attributes"]["title"])))
        except Exception as e:
            title = "NoTitle"
        if not chap == previousChap:
            i += 1
            prgbar.add_task(f"Chapter {chap} volume {vol}", total=len(imgPaths))
            if fsChoice: # FROM {vol}/{chap}/{page}.* to {vol}/{chap}-{page}.*
                for img in imgPaths: # for each image
                    try:
                        with open(f"{name}/chapters/vol-{vol}/chap-{chap}-{title}/page-{imgPaths.index(img)+1}.{fileFormat}", "r+") as ofile:
                            try:
                                with open(f"{name}/chapters/vol-{vol}/chap-{chap}-{title}-p{imgPaths.index(img)+1}.{fileFormat}", "x+") as file:
                                    file.buffer.write(ofile.buffer.read()) 
                            except FileExistsError:
                                pass
                    except FileNotFoundError:
                        pass
                    prgbar.advance(prgbar.task_ids[-1])
                try:
                    for img in os.listdir(f"{name}/chapters/vol-{vol}/chap-{chap}-{title}"):
                        os.remove(f"{name}/chapters/vol-{vol}/chap-{chap}-{title}/{img}")
                    os.rmdir(f"{name}/chapters/vol-{vol}/chap-{chap}-{title}")
                except FileNotFoundError:
                    pass
            # ==============================================================
            else: # FROM {vol}/{chap}-{page}.* to {vol}/{chap}/{page}.*
                for img in imgPaths: # for each image
                    # create folder
                    os.makedirs(f"{name}/chapters/vol-{vol}/chap-{chap}-{title}", exist_ok=True) 
                    try:
                        with open(f"{name}/chapters/vol-{vol}/chap-{chap}-{title}-p{imgPaths.index(img)+1}.{fileFormat}", "r+") as ofile: # or jpg for smaller size
                            try:
                                with open(f"{name}/chapters/vol-{vol}/chap-{chap}-{title}/page-{imgPaths.index(img)+1}.{fileFormat}", "x+") as file: # or jpg for smaller size
                                    file.buffer.write(ofile.buffer.read()) 
                            except FileExistsError:
                                pass
                        os.remove(f"{name}/chapters/vol-{vol}/chap-{chap}-{title}-p{imgPaths.index(img)+1}.{fileFormat}")
                    except FileNotFoundError:
                        pass
                    prgbar.advance(prgbar.task_ids[-1])

            prgbar.remove_task(prgbar.task_ids[-1])
            previousChap = chap     
    prgbar.refresh()
    prgbar.stop()
    print("[bold green]Conversion completed ![/bold green]")   