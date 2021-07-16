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
print("File system convertissor :")
print("\t- This converter uses the infos.json file to gather infos about the settings of the folder")
print("\t- You [bold red]do not[/bold red] need to edit this file")
print("\t- Incomplete archives can be used but [bold red]aren't recommended[/bold red] (can cause problems)")
print("\t- Please don't stop the conversion while in execution as it will break the folder")
print("============================================")
# choice of mangas to convert
folderList = [f for f in os.listdir(os.getcwd()) if os.path.isdir(f) and "." not in f]
if not folderList: # if no folders have been found
    print("No mangas found in working directory !")
    exit()
print("Manga choice :")
for i in range(len(folderList)):
    print(f"\t{i} : {folderList[i]}")
print("============================================")
mChoice = input(f"Choice (all if empty) (space between values): ")
if not mChoice:
    titlelist = folderList
else:
    try:
        titlelist = [folderList[int(i)] for i in mChoice.split(" ")]
    except Exception:
        print("[bold red]Invalid choice[/bold red]")
        exit()
# for each manga
for m in titlelist:
    print(f"[bold blue]{m}[/bold blue]")
    with open(os.path.join(m, "infos.json"), "r", encoding="UTF-8") as file:
        mangaInfos = json.load(file)

    idManga = mangaInfos["id"]
    name = mangaInfos["name"]
    fileFormat = ("png" if int(mangaInfos["format"]) else "jpg")
    print(f"Format : {fileFormat}")
    cfsChoice = int(mangaInfos["fileSys"])
    fsChoice = 0 if cfsChoice else 1
    
    (cfs, fs) = ("vol/chap-page.*", "vol/chap/page.*") if cfsChoice else ("vol/chap/page.*", "vol/chap-page.*")
    print(f"Current file system : [bold green]{cfs}[/bold green]")
    confirm = input(f"\tFile system to convert to : {fs} \n\tIs this correct (y/N) ? ")
    if confirm != "y":
        print(f"[bold red]Conversion of {m} cancelled[/bold red]")
        continue

    mangaInfos["fileSys"] = fsChoice
    with open(os.path.join(m, "infos.json"), "w", encoding="UTF-8") as file:
        json.dump(mangaInfos, file)
            

    with open(os.path.join(name, "chapters.json"), "r", encoding="UTF-8") as file:
        chapters = json.load(file)
        # sort the list from the json to make loading of images in order
        chapters.sort(key=lambda c: (float(c["data"]["attributes"]["chapter"]) 
                                    if c["data"]["attributes"]["chapter"] != None 
                                    else 0))

    print("[italic]Replacing images...[/italic]")
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
                        with open(os.path.join(name, "chapters", f"vol-{vol}", f"chap-{chap}-{title}", f"page-{imgPaths.index(img)+1}.{fileFormat}"), "r+") as ofile:
                            try:
                                with open(os.path.join(name, "chapters", f"vol-{vol}", f"chap-{chap}-{title}-p{imgPaths.index(img)+1}.{fileFormat}"), "x+") as file:
                                    file.buffer.write(ofile.buffer.read()) 
                            except FileExistsError:
                                pass
                    except FileNotFoundError:
                        pass
                    prgbar.advance(prgbar.task_ids[-1])
                try:
                    for img in os.listdir(os.path.join(name, "chapters", f"vol-{vol}", f"chap-{chap}-{title}")):
                        os.remove(os.path.join(name, "chapters", f"vol-{vol}", f"chap-{chap}-{title}", img))
                    os.rmdir(os.path.join(name, "chapters", f"vol-{vol}", f"chap-{chap}-{title}"))
                except FileNotFoundError:
                    pass
            # ==============================================================
            else: # FROM {vol}/{chap}-{page}.* to {vol}/{chap}/{page}.*
                for img in imgPaths: # for each image
                    # create folder
                    os.makedirs(os.path.join(name, "chapters", f"vol-{vol}", f"chap-{chap}-{title}"), exist_ok=True) 
                    try:
                        with open(os.path.join(name, "chapters", f"vol-{vol}", f"chap-{chap}-{title}-p{imgPaths.index(img)+1}.{fileFormat}"), "r+") as ofile: # or jpg for smaller size
                            try:
                                with open(os.path.join(name, "chapters", f"vol-{vol}", f"chap-{chap}-{title}", f"page-{imgPaths.index(img)+1}.{fileFormat}"), "x+") as file: # or jpg for smaller size
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