"""
Simple script using the MangaDex public API to search and get/sync mangas and store it in folders :
    - General infos :
        - don't have to be logged in to use it
        - you can update existant archives easily (U as 1st input)
        - title is asked in console but tags must be added directly into the search payload (l.42)
        - you can choose between two file system to save pictures, but if you want to change afterwards, you can use the FileSys_convert.py script
        - .json files are used to store responses from the server and are kept after sync, so it is possible to read them
        - you can stop the script halfway in and restart it after, it will pass already dowloaded pictures (so the script can update mangas already synced before with only the new content)
Link to the MangaDex API documentation : https://api.mangadex.org/docs.html
    
    Made by Merlet Raphael, 2021
"""

import httpx # async requests
import requests as req
from rich import print # pretty print
from rich.progress import * # progress bar
import json # json handling
import os # IO (mkdir)
import asyncio # used to run async func
from time import perf_counter, time # time is time since Epoch
from multiprocessing.dummy import Pool as ThreadPool # for fast I/O (hopefully)

base = "https://api.mangadex.org"
SIMULTANEOUS_REQUESTS = 10 # should always be under 40 (10 is best)
__VERSION__ = '1.1'

async def get_manga(fsChoice, qChoice, idManga, name):
    """
    called for each chapter concurrently, take care of doing the requests and saving the pages
    """

    payloadManga = {
        "translatedLanguage[]": [
            #"fr", 
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
        n = 'aaaaa'                           
        for c in chapters:
            ni = c["data"]["attributes"]["chapter"]
            if ni == n:
                chapters.remove(c)
            else:
                n = ni

    nNewImgs = 0
    taskId = prgbar.add_task(name, total=len(chapters))
    # setup chapter tasks
    tasks = [get_chapter_data(c, qChoice, name, fsChoice, taskId) for c in chapters]
    for i in range(0, len(chapters), SIMULTANEOUS_REQUESTS):
        results = await asyncio.gather(*tasks[i:i+SIMULTANEOUS_REQUESTS])
        with ThreadPool(15) as pool:
            new_imgs_chap = pool.starmap(save_chapter, (*results,))
            pool.close()
        nNewImgs += sum(new_imgs_chap)
    
    if nNewImgs:
        print(f"[bold blue]{nNewImgs}[/bold blue] images have been added to the [bold red]{name}/chapters/[/bold red] folder")

    prgbar.remove_task(taskId)

async def get_chapter_data(c, quality, name, fsChoice, idTask):
    """
    Get all pages from imgPaths from the chapter with the hash
    args:
        - c : json dictionary with chapter infos
        - quality : bool : if the images are compressed (jpg) or not (png)
        - name : str : name of manga

    output : int : number of added images
    """
    # chapter infos
    vol = c["data"]["attributes"]["volume"]
    chap = c["data"]["attributes"]["chapter"]
    id = c["data"]["id"]
    imgPaths = c["data"]["attributes"][("data" if quality else "dataSaver")] # ["dataSaver"] for jpg (smaller size)
    hash = c["data"]["attributes"]["hash"]
    fileFormat = "png" if quality else "jpg"
    # get the title
    try:
        if not c["data"]["attributes"]["title"]:
            title = "NoTitle"
        title = "".join(list(filter(lambda x: x not in (".", ":", '"', "?", "/"), c["data"]["attributes"]["title"])))
    except Exception:
        title = "NoTitle"
    # check for already downloaded images in directory
    if fsChoice:    
        imgsToGet = [img for img in imgPaths if not os.path.isfile(os.path.join(name, "chapters", f"vol-{vol}", f"chap-{chap}-{title}-p{imgPaths.index(img)+1}.{fileFormat}"))]
    else:
        imgsToGet = [img for img in imgPaths if not os.path.isfile(os.path.join(name, "chapters", f"vol-{vol}", f"chap-{chap}-{title}", f"page-{imgPaths.index(img)+1}.{fileFormat}"))]
    if imgsToGet:
        baseServer = 'https://uploads.mangadex.org'
        # Ask an adress for M@H for each chapter (useless because when not logged in, defaults to 'https://uploads.mangadex.org')
        # If used, make sure it will always use the good adress, but is rate limited at 40 reqs/min and slow to do
        #rServ = httpx.get(f"{base}/at-home/server/{id}", timeout=1000)
        #dataServer = rServ.json()
        #try:
        #    baseServer = dataServer["baseUrl"]
        #except KeyError: # request failed
        #    time_to_wait = float(rServ.headers['x-ratelimit-retry-after']) - time()
        #    await asyncio.sleep(time_to_wait)
        #    rServ = httpx.get(f"{base}/at-home/server/{id}", timeout=1000)
        #    dataServer = rServ.json()
        #    baseServer = dataServer["baseUrl"]
        #dataServer = rServ.json()

        adress = f"{baseServer}/data/{hash}/" if quality else f"{baseServer}/data-saver/{hash}"
        async with httpx.AsyncClient() as client: 
            error_encountered = 1
            while error_encountered:
                try:
                    tasks = (client.get(f"{adress}/{img}", timeout=1000) for img in imgPaths)  
                    reqs = await asyncio.gather(*tasks)
                    images = [rep.content for rep in reqs]
                    error_encountered = 0
                except Exception:
                    continue
    else:
        images = []

    prgbar.update(idTask, description=f'{name} (vol {vol} chap {chap})', advance=1)
    return images, name, vol, chap, title, fileFormat, fsChoice

def save_chapter(images: list[bytes], name, vol, chap, title, fileFormat, fsChoice) -> int:
    """
    called by get_chapter_pages saves the images of the chapter in the correct folder
    param : images : list[bytes] : list of all the pages in bytes
    param : name, vol, chap, title : infos of the chapter

    sortie : int : number of new images saved for this chapter
    """
    new_imgs = 0
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
            new_imgs += 1
        except FileExistsError:
            pass

    return new_imgs


print("============================================")
print(f"Mangadex Downloader/Sync script v{__VERSION__}")
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
    
    if isLink: # links to page (need to get the page)
        links = input("Adress(es) to manga(s) (espaces between each adresses/ids) : ")
        ids = [link.split('/')[-2] if len(link) > 36 else link for link in links.split(' ')]
        payload = {
            "ids[]": ids,
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
        "limit": 9, # numbers of results to choose from (9 by default : 10 results)
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
start = perf_counter()
# for each manga
def get_param_manga(m, fsChoice='', qChoice=''):
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
    
    return fsChoice, qChoice, idManga, name

async def get_all_mangas(mList):
    manga_tasks = (get_manga(*(get_param_manga(m, fsChoice, qChoice) if newSync else get_param_manga(m))) for m in mList)
    await asyncio.gather(*manga_tasks)

asyncio.run(get_all_mangas(mList))

stop = perf_counter()
execution_time = round(stop - start, 3)
print(f"temps d'éxecution : {execution_time}s")
prgbar.refresh()
prgbar.stop()






    
    

    
    

