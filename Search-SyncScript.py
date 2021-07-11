"""
Simple script using the MangaDex public API to search and get/sync mangas and store it in folders :
    - don't have to be logged in to use it
    - title is asked in console but tags must be added directly into the search payload (l.42)
    - the download might be long, and thus a progress bar is rendered using the rich module (must be installed)
    - you can choose between two file system to save pictures, but if you want to change afterward, you can use the FileSys_convert.py script
    - .json files are used to store responses from the server and are kept after sync, so it is possible to read them
    - you can stop the script halfway in and restart it after, it will pass already dowloaded pictures (so the script can update mangas already synced before with only the new content)
    - the mangas folders will be stored in the working directory so be careful of where you launch the script from
    - the script only ask for one result but this can be changed by changing the value in the limit key of the search payload (l.42)
Link to the MangaDex API documentation : https://api.mangadex.org/docs.html
    
    Made by Merlet Raphael, 2021
"""

import requests as req # HTTP requests
from rich import print # pretty print
from rich.progress import * # progress bar
import json # json handling
import os # IO (mkdir)

title = input("Search title : ")
print("============================================")
print("File system :")
print("\t- 0 : vol/chap/page.* : \n\t\teasier to browse but harder to read chapters")
print("\t- 1 : vol/chap-page.* : \n\t\teasier to read chapters but harder to browse")
print("\t- empty : will stop after search (creation of search.json), for convert.py")
print("============================================")
fsChoice = input("Choice (0 or 1 or empty) : ")
if fsChoice: # if not empty
    try:
        fsChoice = int(fsChoice)
        StopAfterSearch = False
    except Exception:
        print("[bold red]Invalid choice[/bold red]")
        exit()
else:
    StopAfterSearch = True

base = "https://api.mangadex.org"

payload = {
    "title": title,
    "limit": 1, # numbers of results wanted
    # tag exemples
#    "includedTags[]": "423e2eae-a7a2-4a8b-ac03-a8351462d71d", # romance
#    "includedTags[]": "e5301a23-ebd9-49dd-a0cb-2add944c7fe9", # SoL
# you can edit this dictionary by adding tags (like above, exemples in tags.json)
}
r = req.get(f"{base}/manga", params=payload)
#print(r.text)
print("Status code search :", r.status_code)

data = r.json()
#print(data)
with open("search.json", "w+", encoding="UTF-8") as file:
    json.dump(data, file)

print("Search results...")
for m in data["results"]:
    print("\t",m["data"]["attributes"]["title"]["en"])

with open("search.json", "r", encoding="UTF-8") as file:
    dataSearch = json.load(file)
    
if StopAfterSearch:   
    exit() # to stop after search (for convert)

# Search confirmation
confimttl = input("Is this correct (y or n) ? ")
if confimttl != "y":
    print("[bold red]Synchronisation cancelled[/bold red]")
    exit()
    
# for each manga
for m in dataSearch["results"]:
    idManga = m["data"]["id"]
    name = "".join(list(filter(lambda x: x not in (".", ":", ",", "?") , m["data"]["attributes"]["title"]["en"])))
    
    payloadManga = {
        "translatedLanguage[]": "fr",
        "translatedLanguage[]": "en",
    }  

    r2 = req.get(f"{base}/manga/{idManga}/aggregate", params=payloadManga)
    print(f"Status code aggregate {name} :", r2.status_code)
    mangaList = r2.json()

    payloadManga["limit"] = 500
    r3 = req.get(f"{base}/manga/{idManga}/feed", params=payloadManga)
    print(f"Status code feed {name} :", r3.status_code)
    mangaFeed = r3.json()

    #print(r2.json())
    if name not in os.listdir(os.getcwd()):
        os.mkdir(f"{os.getcwd()}/{name}")

    with open(f"{name}/aggregate.json", "w+", encoding="UTF-8") as file:
        json.dump(mangaList["volumes"], file)
    
    with open(f"{name}/chapters.json", "w+", encoding="UTF-8") as file:
        json.dump(mangaFeed["results"], file)
    
    with open(f"{name}/chapters.json", "r", encoding="UTF-8") as file:
        chapters = json.load(file)
        # sort the list from the json to make loading of images in order
        chapters.sort(key=lambda c: (float(c["data"]["attributes"]["chapter"]) 
                                    if c["data"]["attributes"]["chapter"] != None 
                                    else 0))                  
    baseServer = ""
    # for each chapter
    i = 0
    nNewImgs = 0
    previousChap = "-1"
    # create progress bar for chapters 
    prgbar = Progress()
    prgbar.start()
    for c in chapters:
        i += 1
        # chapter infos
        vol = c["data"]["attributes"]["volume"]
        chap = c["data"]["attributes"]["chapter"]
        id = c["data"]["id"]
        imgPaths = c["data"]["attributes"]["data"] # ["dataSaver"] for jpg (smaller size)
        hash = c["data"]["attributes"]["hash"]
        try:
            title = "".join(list(filter(lambda x: x not in (".", ":", '"', "?"), c["data"]["attributes"]["title"])))
        except Exception as e:
            title = "NoTitle"
        # check if it's the same chapter, but from another translator
        if not chap == previousChap: 
            prgbar.add_task(f"Chapter {chap} volume {vol} ({round(i/len(chapters)*100, ndigits=1)}%)", total=len(imgPaths))
            #print(f"\tChapter {chap} volume {vol} ({round(i/len(chapters)*100, ndigits=1)}%)")
            if baseServer == "":
                # request to get the M@H server
                rServ = req.get(f"{base}/at-home/server/{id}")
                #print(f"Status code server get {name} :", rServ.status_code)
                dataServer = rServ.json()
                baseServer = dataServer["baseUrl"]
                print(f"Retrieving images from server at {baseServer} ... [italic]This might take a while...[/italic]")
            # for each image
            for img in imgPaths:
                #print(f"\t\tpage {imgPaths.index(img)+1}...")
                # save image
                try:
                    if fsChoice:
                        # NORMAL FILE SYSTEM ({vol}/{chap}-{page}.*)
                        # (easier for browsing pictures but harder to view in explorer)
                        try:
                            os.makedirs(f"{name}/chapters/vol-{vol}") # create folder
                        except Exception:
                            pass
                        with open(f"{name}/chapters/vol-{vol}/chap-{chap}-{title}-p{imgPaths.index(img)+1}.png", "x+") as file: # jpg for smaller size
                            # request to get the image if not already downloaded
                            rImg = req.get(f"{baseServer}/data/{hash}/{img}")
                            #rImg = req.get(f"{baseServer}/data-saver/{hash}/{img}") # jpg (smaller size)
                            # write data to file
                            #print(rImg.content)
                            file.buffer.write(rImg.content)
                            nNewImgs += 1
                    else:
                        # ==============================================================
                        # OTHER FILE SYSTEM ({vol}/{chap}/{page}.*)
                        # (easier for browsing in explorer but reading is harder)
                        try:
                            os.makedirs(f"{name}/chapters/vol-{vol}/chap-{chap}-{title}") # create folder
                        except Exception:
                            pass
                        with open(f"{name}/chapters/vol-{vol}/chap-{chap}-{title}/page-{imgPaths.index(img)+1}.png", "x+") as file: # jpg for smaller size
                            # request to get the image if not already downloaded
                            rImg = req.get(f"{baseServer}/data/{hash}/{img}")
                            #rImg = req.get(f"{baseServer}/data-saver/{hash}/{img}") # jpg (smaller size)
                            # write data to file
                            #print(rImg.content)
                            file.buffer.write(rImg.content)
                except FileExistsError:
                    pass
                prgbar.advance(prgbar.task_ids[-1])
            prgbar.remove_task(prgbar.task_ids[-1])
            previousChap = chap
    prgbar.refresh()
    prgbar.stop()
    print(f"{name} have been successfully synced from MangaDex !")
    print(f"\t{nNewImgs} images have been added to the {name}/chapters/ folder")






    
    

    
    

