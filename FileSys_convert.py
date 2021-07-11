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
confimttl = input(f"Mangas to convert : {titlelist} \n\tIs this correct (y or n) ? ")
if confimttl != "y":
    print("Conversion cancelled")
    exit()
# Choice of file system
print("============================================")
print("File system to convert to :")
print("\t- 0 : [bold red]vol/chap/page.*[/bold red] : \n\t\teasier to browse but harder to read chapters")
print("\t- 1 : [bold red]vol/chap-page.*[/bold red] : \n\t\teasier to read chapters but harder to browse")
print("============================================")
try:
    fsChoice = int(input("Choice (0 or 1) : "))
    if fsChoice not in (0, 1):
        print(f"Invalid choice '{fsChoice}'")
        exit()
except Exception:
    print("Invalid choice")
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
                        with open(f"{name}/chapters/vol-{vol}/chap-{chap}-{title}/page-{imgPaths.index(img)+1}.png", "r+") as ofile:
                            try:
                                with open(f"{name}/chapters/vol-{vol}/chap-{chap}-{title}-p{imgPaths.index(img)+1}.png", "x+") as file:
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
                        with open(f"{name}/chapters/vol-{vol}/chap-{chap}-{title}-p{imgPaths.index(img)+1}.png", "r+") as ofile: # or jpg for smaller size
                            try:
                                with open(f"{name}/chapters/vol-{vol}/chap-{chap}-{title}/page-{imgPaths.index(img)+1}.png", "x+") as file: # or jpg for smaller size
                                    file.buffer.write(ofile.buffer.read()) 
                            except FileExistsError:
                                pass
                        os.remove(f"{name}/chapters/vol-{vol}/chap-{chap}-{title}-p{imgPaths.index(img)+1}.png")
                    except FileNotFoundError:
                        pass
                    prgbar.advance(prgbar.task_ids[-1])

            prgbar.remove_task(prgbar.task_ids[-1])
            previousChap = chap     
    prgbar.refresh()
    prgbar.stop()
    print("[bold green]Conversion completed ![/bold green]")   