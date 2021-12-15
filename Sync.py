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
from time import perf_counter, sleep, time # time is time since Epoch
from threading import Thread # Permet de faire tourner des fonctions en meme temps (async)
from Globals import __AUTHOR__, __VERSION__, FOLDER_PATH, format_title, SIMULTANEOUS_REQUESTS

base = "https://api.mangadex.org" # base adress for the API endpoints

def get_manga(*args):
    """
    called for each chapter concurrently, take care of doing the requests and saving the pages
    """
    (fsChoice, qChoice, idManga, name, presentChapters) = args
    payloadManga = {
        "translatedLanguage[]": [
            #"fr", 
            "en"
        ],
        "limit": 500,
        "offset": 0,
        "includeFutureUpdates": "0"
    }  
    
    with open(os.path.join(FOLDER_PATH, name, "chapters.json"), "w+", encoding="UTF-8") as file:
        r3 = req.get(f"{base}/manga/{idManga}/feed", params=payloadManga)
        mangaFeed = r3.json()
        chapters = mangaFeed['data']
        # if manga have 500+ chapters
        while mangaFeed['total'] > (len(mangaFeed['data']) + 500*mangaFeed['offset']):
            mangaFeed['offset'] += 1 
            r3 = req.get(f"{base}/manga/{idManga}/feed", params=payloadManga)
            mangaFeed = r3.json()
            chapters += mangaFeed['data']

        json.dump(chapters, file)

    with open(os.path.join(FOLDER_PATH, name, "chapters.json"), "r", encoding="UTF-8") as file:
        chapters = json.load(file)
        # sort the list from the json to make loading of images in order
        chapters.sort(key=lambda c: (float(c["attributes"]["chapter"]) 
                                    if c["attributes"]["chapter"] != None
                                    else 0))       
        # remove duplicates and already present chapters                     
        n = 'aaaaa'                           
        for c in chapters:
            ni = c["attributes"]["chapter"]
            if ni == n:
                chapters.remove(c)
            else:
                n = ni
        chapters = [c for c in chapters if str(c["attributes"]["chapter"]) not in presentChapters and c["attributes"]["data"]]

    taskId = prgbar.add_task(name, total=len(chapters) if chapters else 1)
    if not chapters: # if there is no new chapters, fill progress bar and quit func
        prgbar.update(taskId, description=f'{name} (no new chapters)', advance=1)
        sleep(1.0)
        prgbar.remove_task(taskId)
        return
    # setup chapter tasks
    done_tasks = 0
    tasks = [Thread(target=get_chapter_data, args=(c, qChoice, name, fsChoice, taskId)) 
            for c in chapters[:SIMULTANEOUS_REQUESTS]]
    initial_tasks = len(tasks)
    for task in tasks:    
        task.start()
    not_done = True
    while not_done:
        for task in tasks:
            if not task.is_alive():
                if len(chapters) < initial_tasks + done_tasks: # if there is remaining tasks to add
                    i = tasks.index(task)
                    c = chapters[SIMULTANEOUS_REQUESTS + done_tasks]
                    new_task = Thread(target=get_chapter_data, args=(c, qChoice, name, fsChoice, taskId))
                    new_task.start()
                    tasks[i] = new_task
                    done_tasks += 1
                else:
                    not_done = False
        sleep(.1)
    while any([task.is_alive() for task in tasks]): sleep(.1)

    with open(f"{FOLDER_PATH}/{name}/infos.json", "w+", encoding="UTF-8") as file: # updates infos.json for new chapters
        newPresentChapters = list(set([chapter["attributes"]["chapter"] for chapter in chapters if chapter["attributes"]["data"]]))
        newPresentChapters.sort(key=lambda c: (float(c) if c != None else 0))
        mangaInfos = {
            "fileSys" : fsChoice,
            "format" : qChoice,
            "id": idManga,
            "name" : name,
            "chapterList": presentChapters + newPresentChapters
        }
        json.dump(mangaInfos, file)

    prgbar.update(taskId, description=f'{name} ({len(chapters)} new chapters)', advance=1)

def get_chapter_data(*args):
    """
    Get all pages from imgPaths from the chapter with the hash
    args:
        - c : json dictionary with chapter infos
        - quality : bool : if the images are compressed (jpg) or not (png)
        - name : str : name of manga

    output : int : number of added images
    """
    (c, quality, name, fsChoice, idTask) = args

    async def request_images() -> list:
        """
        requests the image to a server asynchronously
        """
        #print("request_images chap {} vol {}".format(chap, vol))
        baseServer = 'https://uploads.mangadex.org'
        # Ask an adress for M@H for each chapter (useless because when not logged in, defaults to 'https://uploads.mangadex.org')
        # If used, make sure it will always use the good adress, but is rate limited at 40 reqs/min and slow to do
        #rServ = httpx.get(f"{base}/at-home/server/{id}", timeout=1000)
        #dataServer = rServ.json()
        #try:
        #    baseServer = dataServer["baseUrl"]
        #except KeyError: # request failed
        #    time_to_wait = float(rServ.headers['X-RateLimit-Retry-After']) - time()
        #    await asyncio.sleep(time_to_wait)
        #    rServ = httpx.get(f"{base}/at-home/server/{id}", timeout=1000)
        #    dataServer = rServ.json()
        #    baseServer = dataServer["baseUrl"]
        #dataServer = rServ.json()

        adress = f"{baseServer}/data/{hash}/" if quality else f"{baseServer}/data-saver/{hash}"
        async with httpx.AsyncClient() as client: 
            error_encountered = 1
            retries_left = 5
            while error_encountered:
                try:
                    tasks = (client.get(f"{adress}/{img}", timeout=1000) for img in imgsToGet)  
                    reqs = await asyncio.gather(*tasks)
                    for rep in reqs:
                        rep.raise_for_status()
                    images = [rep.content for rep in reqs]
                    error_encountered = 0
                except Exception as e:
                    print(f'An exception occurred when gathering chap {chap} images : {e} (will retry {retries_left} more times)')
                    retries_left -= 1
                    if retries_left:
                        await asyncio.sleep(1)
                        continue
                    else:
                        print(f"Chap {chap} ignored because 5 exceptions occured")
                        images = []
                        break
        return images
    # chapter infos
    vol = c["attributes"]["volume"]
    chap = c["attributes"]["chapter"]
    imgPaths = c["attributes"][("data" if quality else "dataSaver")] # ["dataSaver"] for jpg (smaller size)
    hash = c["attributes"]["hash"]
    fileFormat = "png" if quality else "jpg"
    # get the title
    try:
        if not c["attributes"]["title"]:
            title = "NoTitle"
        title = format_title(c["attributes"]["title"])
    except Exception:
        title = "NoTitle"
    # check for already downloaded images in directory
    if fsChoice:    
        imgsToGet = [img for img in imgPaths if not os.path.exists(os.path.join(FOLDER_PATH, name, "chapters", f"vol-{vol}", f"chap-{chap}-{title}-p{imgPaths.index(img)+1}.{fileFormat}"))]
    else:
        imgsToGet = [img for img in imgPaths if not os.path.exists(os.path.join(FOLDER_PATH, name, "chapters", f"vol-{vol}", f"chap-{chap}-{title}", f"page-{imgPaths.index(img)+1}.{fileFormat}"))]
    if imgsToGet:
        loop = asyncio.new_event_loop()
        images = loop.run_until_complete(request_images())
    else:
        images = []

    prgbar.update(idTask, description=f'{name} (vol {vol} chap {chap})', advance=1)
    task = Thread(target=save_chapter, args=(images, name, vol, chap, title, fileFormat, fsChoice))
    task.start()
    task.join()

def save_chapter(*args) -> int:
    """
    called by get_chapter_pages saves the images of the chapter in the correct folder
    param : images : list[bytes] : list of all the pages in bytes
    param : name, vol, chap, title : infos of the chapter

    sortie : int : number of new images saved for this chapter
    """
    (images, name, vol, chap, title, fileFormat, fsChoice) = args
    new_imgs = 0
    for img in images:
        try:
            if fsChoice:
                # NORMAL FILE SYSTEM ({vol}/{chap}-{page}.*)
                # (easier for browsing pictures but harder to view in explorer)
                try:
                    os.makedirs(os.path.join(FOLDER_PATH, name, "chapters", f"vol-{vol}")) # create folder
                except Exception:
                    pass
                with open(os.path.join(FOLDER_PATH, name, "chapters", f"vol-{vol}", f"chap-{chap}-{title}-p{images.index(img)+1}.{fileFormat}"), "x+") as file:
                    # write data to file
                    file.buffer.write(img)
            else:
                # ==============================================================
                # OTHER FILE SYSTEM ({vol}/{chap}/{page}.*)
                # (easier for browsing in explorer but reading is harder)
                try:
                    os.makedirs(os.path.join(FOLDER_PATH, name, "chapters", f"vol-{vol}", f"chap-{chap}-{title}")) # create folder
                except Exception:
                    pass
                with open(os.path.join(FOLDER_PATH, name, "chapters", f"vol-{vol}", f"chap-{chap}-{title}", f"page-{images.index(img)+1}.{fileFormat}"), "x+") as file:
                    # write data to file
                    file.buffer.write(img)
            new_imgs += 1
        except FileExistsError:
            pass

    return new_imgs

print("============================================")
print(f"Mangadex Downloader/Sync script v{__VERSION__}")
print(f"By {__AUTHOR__}")
print("============================================")
choices = input("[S]earch for a new manga // [U]pdate existant one // [V]erify folder state \n\t(S/U/V) ([V]erify only by default) ? ").split(' ')
newSync = (1 if "S" in choices else 0)
isUpdate = (1 if "U" in choices else 0)

# User interaction
if newSync: # Search for a new manga and ask for storage choices
    print("============================================")
    print("Search type :")
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
    
    else: # search engine
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
            "hasAvailableChapters": "1",
            "order[relevance]": "desc"
            # tag exemples
            #"includedTags[]": [
            #    "423e2eae-a7a2-4a8b-ac03-a8351462d71d", # romance
            #    "e5301a23-ebd9-49dd-a0cb-2add944c7fe9", # SoL
            #    "caaa44eb-cd40-4177-b930-79d3ef2afe87" # School
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
    if data["data"]: # results found
        for i in range(len(data["data"])):
            title = data["data"][i]["attributes"]["title"]["en"] if "en" in data["data"][i]["attributes"]["title"].keys() else list(data["data"][i]["attributes"]["title"].values())[0]
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
            mList = [dataSearch["data"][int(i)-1] for i in mChoice.split(" ")]
        except Exception:
            print("[bold red]Invalid choice")
            exit()
    else:
        mList = dataSearch["data"]
    
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
    folderList = [f for f in os.listdir(os.path.join(FOLDER_PATH)) if os.path.isdir(os.path.join(FOLDER_PATH, f)) and "infos.json" in os.listdir(os.path.join(FOLDER_PATH, f))]
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
    
    nChanges = 0
    for m in mList:
        chapterList = []
        for vol in [f for f in os.listdir(os.path.join(FOLDER_PATH, m, "chapters")) if os.path.isdir(os.path.join(FOLDER_PATH, m, "chapters", f))]:
            volChapList = [chap.split('-')[1] for chap in os.listdir(os.path.join(FOLDER_PATH, m, "chapters", vol))]
            chapterList.extend(volChapList)
        chapterList = list(set(chapterList))
        chapterList.sort(key=lambda c: (float(c) if c != None and c != 'None' else 0))
        with open(os.path.join(FOLDER_PATH, m, "infos.json"), "r", encoding="UTF-8") as file:
            mangaInfos = json.load(file)
        if chapterList != mangaInfos['chapterList']:
            mangaInfos['chapterList'] = chapterList
            with open(os.path.join(FOLDER_PATH, m, "infos.json"), "w+", encoding="UTF-8") as file:
                json.dump(mangaInfos, file)
            nChanges += 1
    print('[bold blue]{} changes to infos.json files have been made'.format((nChanges if nChanges else 'No')))
    if not isUpdate:
        exit()
        
# create progress bar for mangas
prgbar = Progress()
prgbar.start()
start = perf_counter()
# for each manga
def get_param_manga(m, fsChoice='', qChoice=''):
    if newSync:
        presentChapters = []
        idManga = m["id"]
        name = format_title(m["attributes"]["title"]["en"] if "en" in m["attributes"]["title"].keys() else list(m["attributes"]["title"].values())[0])
        if name not in os.listdir(FOLDER_PATH):
            os.makedirs(os.path.join(FOLDER_PATH, name), exist_ok=True)
        try:
            with open(os.path.join(FOLDER_PATH, name, "infos.json"), "x+", encoding="UTF-8") as file:
                mangaInfos = {
                    "fileSys" : fsChoice,
                    "format" : qChoice,
                    "id": idManga,
                    "name" : name,
                    "chapterList": presentChapters
                }
                json.dump(mangaInfos, file)
        except FileExistsError: pass
    
    else:
        name = m
        with open(os.path.join(FOLDER_PATH, name, "infos.json"), "r", encoding="UTF-8") as file:
            mangaInfos = json.load(file)
        idManga = mangaInfos["id"]
        qChoice = mangaInfos["format"]
        fsChoice = mangaInfos["fileSys"]
        if "chapterList" in mangaInfos.keys(): # updated infos.json
            presentChapters = mangaInfos["chapterList"]
        else: # old infos.json, need to add present chapters
            with open(os.path.join(FOLDER_PATH, name, "chapters.json"), "r", encoding="UTF-8") as file:
                chapters = json.load(file)   
                chapters.sort(key=lambda c: (float(c["attributes"]["chapter"]) 
                                    if c["attributes"]["chapter"] != None 
                                    else 0))      
                presentChapters = list(set([chapter["attributes"]["chapter"] for chapter in chapters]))
                presentChapters.sort(key=lambda c: (float(c) if c != None else 0))
            with open(os.path.join(FOLDER_PATH, name, "infos.json"), "w+", encoding="UTF-8") as file:
                mangaInfos = {
                    "fileSys" : fsChoice,
                    "format" : qChoice,
                    "id": idManga,
                    "name" : name,
                    "chapterList": presentChapters
                }
                json.dump(mangaInfos, file)
    
    return fsChoice, qChoice, idManga, name, presentChapters

manga_tasks = [Thread(target=get_manga, args=get_param_manga(m, fsChoice, qChoice) if newSync 
                    else get_param_manga(m)) for m in mList]
for task in manga_tasks:
    task.start()

while any([task.is_alive() for task in manga_tasks]):
    sleep(.5)

stop = perf_counter()
execution_time = round(stop - start, 3)
print(f"temps d'éxecution : {execution_time}s")
prgbar.refresh()
prgbar.stop()
