"""
Simple script using the MangaDex public API to search and get/sync mangas and store it in folders :
    - General infos :
        - don't have to be logged in to use it
        - you can update existant archives easily (U as 1st input)
        - title is asked in console but tags must be added directly into the search payload (l.42)
        - you can choose between two file system to save pictures, but if you want to change afterward, you can use the FileSys_convert.py script
        - .json files are used to store responses from the server and are kept after sync, so it is possible to read them
        - you can stop the script halfway in and restart it after, it will pass already dowloaded pictures (so the script can update mangas already synced before with only the new content)
Link to the MangaDex API documentation : https://api.mangadex.org/docs.html
    
    Made by Merlet Raphael, 2021
"""

import requests as req # HTTP requests
from rich import print # pretty print
from rich.progress import * # progress bar
import json # json handling
import os # IO (mkdir)
from getChapter import getPages # async func to get pages
import asyncio # used to run async func

base = "https://api.mangadex.org"

print("============================================")
print("Mangadex Downloader/Sync script")
print("By Merlet Raphaël")
print("============================================")
newSync = (1 if input("[S]earch for a new manga (or [U]pdate existant one) (S/U) ? ") == "S" else 0)

# User interaction
if newSync: # Search for a new manga and ask for storage choices
    print("============================================")
    print("Search term :")
    print("\t- 0 : Search engine")
    print("\t- 1 : Link to manga page")
    print("============================================")
    isLink = input("Choice (0 or 1) : ")
    try:
        isLink = int(isLink)
    except Exception:
        print("[bold red]Invalid choice")
        exit()
    
    if isLink: # link to page (need to get the page)
        id = input("Adress to manga : ")[-36:]
        payload = {
            "ids[]": [id],
            "contentRating[]": [
                "safe",
                "suggestive",
                "erotica",
                "pornographic"
            ]
        }
    else:
        title = input("Search title : ")
        payload = {
        "title": title,
        "limit": 9, # numbers of results to choose from (5 by default)
        "offset": 0,
        "contentRating[]": [
            "safe",
            "suggestive",
            "erotica",
            "pornographic"
        ],
        # tag exemples
        #"includedTags[]": [
        #    "423e2eae-a7a2-4a8b-ac03-a8351462d71d", # romance
        #    "e5301a23-ebd9-49dd-a0cb-2add944c7fe9", # SoL
        #]
        # you can edit this dictionary by adding tags (like above, exemples in tags.json)
        }

    r = req.get(f"{base}/manga", params=payload)
    #print(r.text)
    print("Status code search :", r.status_code)

    data = r.json()
    #print(data)
    with open("search.json", "w+", encoding="UTF-8") as file:
        json.dump(data, file)

    print("============================================")
    print(f"Search results... (results {data['offset']+1} to {data['offset']+data['limit']})")
    if data["results"]: # results found
        for i in range(len(data["results"])):
            title = data["results"][i]["data"]["attributes"]["title"]["en"]
            print(f"\t{i+1} : {title}")
    else: # no results found
        print("\t[bold red]No results !")
        exit()
    print("============================================")
    
    
    with open("search.json", "r", encoding="UTF-8") as file:
        dataSearch = json.load(file)

    # Search choice
    mChoice = input(f"Choice (all if empty // space between values): ")
    if mChoice:
        try:
            mList = [dataSearch["results"][int(i)-1] for i in mChoice.split(" ")]
        except Exception:
            print("[bold red]Invalid choice")
            exit()
    else:
        mList = dataSearch["results"]
    
    print("============================================")
    print("[bold green]File system :")
    print("\t- 0 : vol/chap/page.* : \n\t\teasier to browse but harder to read chapters")
    print("\t- 1 : vol/chap-page.* : \n\t\teasier to read chapters but harder to browse")
    print("============================================")
    fsChoice = input("Choice (0 or 1) : ")
    try:
        fsChoice = int(fsChoice)
    except Exception:
        print("[bold red]Invalid choice")
        exit()
    # ask for file quality if the script doesn't stop after search
    print("============================================")
    print("[bold green]File quality :[/bold green]")
    print("\t- 0 : jpg files (compressed) : smaller by around 20-30%")
    print("\t- 1 : png files (orginal quality) : normal size")
    print("============================================")
    qChoice = input("Choice (0 or 1) : ")
    try:
        qChoice = int(qChoice)
    except Exception:
        print("[bold red]Invalid choice")
        exit()

else: # Ask which manga(s) must be updated
    folderList = [f for f in os.listdir(os.getcwd()) if os.path.isdir(f) and "infos.json" in os.listdir(f)]
    if not folderList: # if no folders have been found
        print("[bold red]No mangas found in working directory !")
        exit()
    print("============================================")
    print("Manga choice :")
    for i in range(len(folderList)):
        print(f"\t{i} : {folderList[i]}")
    print("============================================")
    mChoice = input(f"Choice (all if empty) (space between values): ")
    if not mChoice:
        mList = folderList
    else:
        try:
            mList = [folderList[int(i)] for i in mChoice.split(" ")]
        except Exception:
            print("[bold red]Invalid choice")
            exit()
# create progress bar for mangas
prgbar = Progress()
prgbar.start()
# for each manga
for m in mList:
    # get necessary infos (by search.json or by infos.json)
    if newSync:
        idManga = m["data"]["id"]
        name = "".join(list(filter(lambda x: x not in (".", ":", ",", "?", '/') , m["data"]["attributes"]["title"]["en"])))
        if name not in os.listdir(os.getcwd()):
            os.mkdir(f"{os.getcwd()}/{name}")
        try:
            with open(f"{name}/infos.json", "x+", encoding="UTF-8") as file:
                mangaInfos = {
                    "fileSys" : fsChoice,
                    "format" : qChoice,
                    "id": idManga,
                    "name" : name
                }
                json.dump(mangaInfos, file)
        except FileExistsError: pass
    
    else:
        name = m
        with open(os.path.join(name, "infos.json"), "r", encoding="UTF-8") as file:
            mangaInfos = json.load(file)
        idManga = mangaInfos["id"]
        qChoice = mangaInfos["format"]
        fsChoice = mangaInfos["fileSys"]

    payloadManga = {
        "translatedLanguage[]": [
#            "fr", 
            "en"
        ],
        "limit": 500,
        "offset": 0
    }  
    
    with open(f"{name}/chapters.json", "w+", encoding="UTF-8") as file:
        r3 = req.get(f"{base}/manga/{idManga}/feed", params=payloadManga)
        mangaFeed = r3.json()
        chapters = mangaFeed['results']
        # if manga have 500+ chapters
        while mangaFeed['total'] > (len(mangaFeed['results']) + 500*mangaFeed['offset']):
            mangaFeed['offset'] += 1 
            r3 = req.get(f"{base}/manga/{idManga}/feed", params=payloadManga)
            mangaFeed = r3.json()
            chapters += mangaFeed['results']

        json.dump(chapters, file)

    with open(f"{name}/chapters.json", "r", encoding="UTF-8") as file:
        chapters = json.load(file)
        # sort the list from the json to make loading of images in order
        chapters.sort(key=lambda c: (float(c["data"]["attributes"]["chapter"]) 
                                    if c["data"]["attributes"]["chapter"] != None 
                                    else 0))              
    # for each chapter
    i = 0
    nNewImgs = 0
    previousChap = ""
    # add manga task
    prgbar.add_task(f"{name} (vol 1 chap 1)", total=len(chapters))
    for c in chapters:
        i += 1
        # chapter infos
        vol = c["data"]["attributes"]["volume"]
        chap = c["data"]["attributes"]["chapter"]
        id = c["data"]["id"]
        imgPaths = c["data"]["attributes"][("data" if qChoice else "dataSaver")] # ["dataSaver"] for jpg (smaller size)
        hash = c["data"]["attributes"]["hash"]
        fileFormat = "png" if qChoice else "jpg"
        try:
            if not c["data"]["attributes"]["title"]:
                title = "NoTitle"
            title = "".join(list(filter(lambda x: x not in (".", ":", '"', "?", "/"), c["data"]["attributes"]["title"])))
        except Exception as e:
            title = "NoTitle"
        # check if it's the same chapter, but from another translator
        if not chap == previousChap: 
            # check for already downloaded images in directory
            if fsChoice:    
                imgToGet = [img for img in imgPaths if not os.path.isfile(os.path.join(name, "chapters", f"vol-{vol}", f"chap-{chap}-{title}-p{imgPaths.index(img)+1}.{fileFormat}"))]
            else:
                imgToGet = [img for img in imgPaths if not os.path.isfile(os.path.join(name, "chapters", f"vol-{vol}", f"chap-{chap}-{title}", f"page-{imgPaths.index(img)+1}.{fileFormat}"))]
            if imgToGet: # if there are images to get
                # request to get the M@H server
                rServ = req.get(f"{base}/at-home/server/{id}")
                dataServer = rServ.json()
                baseServer = dataServer["baseUrl"]
                # do all the requests to get the images (bytes)
                images = asyncio.run(getPages(imgToGet, hash, baseServer, qChoice)) 
            else: images = []
            # save all images
            for img in images:
                try:
                    if fsChoice:
                        # NORMAL FILE SYSTEM ({vol}/{chap}-{page}.*)
                        # (easier for browsing pictures but harder to view in explorer)
                        try:
                            os.makedirs(os.path.join(name, "chapters", f"vol-{vol}")) # create folder
                        except Exception:
                            pass
                        with open(os.path.join(name, "chapters", f"vol-{vol}", f"chap-{chap}-{title}-p{images.index(img)+1}.{fileFormat}"), "x+") as file:
                            # write data to file
                            file.buffer.write(img)
                    else:
                        # ==============================================================
                        # OTHER FILE SYSTEM ({vol}/{chap}/{page}.*)
                        # (easier for browsing in explorer but reading is harder)
                        try:
                            os.makedirs(os.path.join(name, "chapters", f"vol-{vol}", f"chap-{chap}-{title}")) # create folder
                        except Exception:
                            pass
                        with open(os.path.join(name, "chapters", f"vol-{vol}", f"chap-{chap}-{title}", f"page-{images.index(img)+1}.{fileFormat}"), "x+") as file:
                            # write data to file
                            file.buffer.write(img)
                    nNewImgs += 1
                except FileExistsError:
                    pass
        prgbar.update(prgbar.task_ids[-1], description=f"{name} (vol {vol} chap {chap})", advance=1)
        previousChap = chap
    if nNewImgs:
        print(f"{name} have been successfully synced from MangaDex !")
        print(f"\t{nNewImgs} images have been added to the {name}/chapters/ folder")

prgbar.refresh()
prgbar.stop()






    
    

    
    

