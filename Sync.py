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
from getpass import getpass # to get password without echo on terminal
from time import perf_counter, sleep, time # time is time since Epoch
from threading import Thread # Permet de faire tourner des fonctions en meme temps (async)
from Globals import __AUTHOR__, __VERSION__, FOLDER_PATH, LOGIN_PATH, format_title, SIMULTANEOUS_REQUESTS

base = "https://api.mangadex.org" # base adress for the API endpoints

class Account:
    """classe qui gère le login et la validité du token, et renvoie le bearer de connexion"""
    def __init__(self, login_path=LOGIN_PATH) -> None:
        self.login_path = login_path
        self.connected = False
        self._token = ""
        self.user = ""
        self._refresh_token = ""
        self._refresh_token = ""
        self.last_check = time() - 15 * 60
            
    def login(self):
        """front login func (console input)"""
        username = input('username : ')
        password = getpass('password : ')   
        self.user = username
        self.pwd = password
        self._token, self._refresh_token = self.__login()
        self.last_check = time()
        with open(self.login_path, 'w+' if os.path.exists(self.login_path) else 'x+') as file:
            txt = {
                'token': self._token,
                'refresh_token': self._refresh_token
            }
            json.dump(txt, file)
        
        return self._token, self._refresh_token
    
    def relogin(self, token: str, refresh_token: str):
        """front relogin func, using __refresh_token if necessary (if valid refresh token found at login_path)"""
        self._token = token
        self._refresh_token = refresh_token
        if not self.check_token():
            self._token, self._refresh_token = self.__refresh_login()
        self.last_check = time()
        self.connected = True
        return self._token

    def __login(self):
        """back login func"""
        payload = {
            'username': self.user,
            'email': self.user,
            'password': self.pwd
        }

        rep = req.post(f'{base}/auth/login', json=payload)
        repJson = rep.json()
        assert repJson['result'] == 'ok', 'login failed (invalid credentials ?) : {}'.format(repJson) # check if login succeded
        print('[bold green]login succeded...')
        self.connected = True
        return repJson['token']['session'], repJson['token']['refresh']

    def check_token(self) -> bool:
        hdrs = {'Authorization': 'Bearer ' + self._token}
        self.last_check = time()
        return req.get(f'{base}/auth/check', headers=hdrs).json()['isAuthenticated']

    def __refresh_login(self):
        rep = req.post(f'{base}/auth/refresh', json={'token': self._refresh_token})
        repJson = rep.json()
        if repJson['result'] == 'ok':
            return repJson['token']['session'], repJson['token']['refresh']
        else:
            return self.__login() if self.user else self.login()

    @property
    def token(self):
        if time() - self.last_check > 14 * 60:
            if not self.check_token():
                self._token, self._refresh_token = self.__refresh_login()
        return self._token
    
    @property
    def bearer(self):
        return {'Authorization': 'Bearer ' + self.token} if self.connected else {}

def get_manga(*args):
    """
    called for each chapter concurrently, take care of doing the requests and saving the pages
    """
    client = httpx.Client(headers=account.bearer)
    #print(client.headers)
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
        r3 = client.get(f"{base}/manga/{idManga}/feed", params=payloadManga)
        while r3.status_code == 429:
            sleep(1.0)
            r3 = client.get(f"{base}/manga/{idManga}/feed", params=payloadManga)
        mangaFeed = r3.json()
        chapters = mangaFeed['data']
        # if manga have 500+ chapters
        while mangaFeed['total'] > (len(mangaFeed['data']) + 500*mangaFeed['offset']):
            mangaFeed['offset'] += 1 
            r3 = client.get(f"{base}/manga/{idManga}/feed", params=payloadManga)
            while r3.status_code == 429:
                sleep(1.0)
                r3 = client.get(f"{base}/manga/{idManga}/feed", params=payloadManga)
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
        all_chaps = [*chapters]
        chapters = [c for c in chapters if str(c["attributes"]["chapter"]) not in presentChapters]

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
            #print(len(chapters))
            #print(initial_tasks + done_tasks)
            if not task.is_alive():
                if len(chapters) > initial_tasks + done_tasks: # if there is remaining tasks to add
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
        newPresentChapters = list(set([chapter["attributes"]["chapter"] for chapter in chapters]))
        newPresentChapters.sort(key=lambda c: (float(c) if c != None else 0))
        try:
            # get scan groups id list
            grp_id_list = list(set([
                [r['id'] for r in c["relationships"] if r['type'] == "scanlation_group"][0]
                for c in all_chaps
            ]))
            # get scan groups name by requests
            rep = client.get(f"{base}/group", params={'limit': 100, 'ids[]': grp_id_list, "order[name]": "asc"})
            grps = {group['attributes']['name']: group['id'] for group in rep.json()['data']}
            # do a dict (id -> chapters)
            grp_per_chaps = {name: [] for name,_ in grps.items()}
            for grp_name, grp_id in grps.items():
                for c in all_chaps:
                    if grp_id in [r['id'] for r in c["relationships"] if r['type'] == "scanlation_group"]:
                        grp_per_chaps[grp_name].append(c["attributes"]["chapter"])
        except Exception:
            pass
        
        mangaInfos = {
            "fileSys" : fsChoice,
            "format" : qChoice,
            "id": idManga,
            "name" : name,
            "chapterList": presentChapters + newPresentChapters,
            "scanlator groups, by chapters done (credits)" : grp_per_chaps
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
    sync_client = httpx.Client(headers=account.bearer)

    async def request_images() -> list:
        """
        requests the image to a server asynchronously
        """
        atHome_payload = {'forcePort443': True}
        #print("request_images chap {} vol {}".format(chap, vol))
        baseServer = 'https://uploads.mangadex.org'
        # Ask an adress for M@H for each chapter
        # Will make sure it will always use the good adress, but is rate limited at 40 reqs/min and slow to do
        rServ = sync_client.get(f"{base}/at-home/server/{id}", timeout=1000, params=atHome_payload)
        
        while rServ.status_code == 429 or rServ.json()['result'] != 'ok': # request failed
            if 'X-RateLimit-Retry-After' in rServ.headers.keys():
                time_to_wait = float(rServ.headers['X-RateLimit-Retry-After']) - time()
            else:
                time_to_wait = 10.0
            await asyncio.sleep(time_to_wait)
            #sync_client.headers = account.bearer # check if token is still valid
            rServ = sync_client.get(f"{base}/at-home/server/{id}", timeout=1000, params=atHome_payload)
            
        dataServer = rServ.json()
        baseServer = dataServer["baseUrl"]
        hash = dataServer["chapter"]["hash"]
        imgPaths = dataServer["chapter"][("data" if quality else "dataSaver")] # ["dataSaver"] for jpg (smaller size)
        # filtering of existent images
        if fsChoice:    
            imgsToGet = [img for img in imgPaths 
            if not os.path.exists(
                os.path.join(FOLDER_PATH, name, "chapters", f"vol-{vol}", 
                            f"chap-{chap}-{title}-p{imgPaths.index(img)+1}.{fileFormat}"))]
        else:
            imgsToGet = [img for img in imgPaths 
            if not os.path.exists(
                os.path.join(FOLDER_PATH, name, "chapters", f"vol-{vol}",
                            f"chap-{chap}-{title}", f"page-{imgPaths.index(img)+1}.{fileFormat}"))]
        # if there is no images to get, exits
        if not imgsToGet:
            return []
        # else, setup an async client and gather the images
        adress = f"{baseServer}/data/{hash}/" if quality else f"{baseServer}/data-saver/{hash}"
        async with httpx.AsyncClient() as client:
            retries_left = 5
            tasks = (client.get(f"{adress}/{img}", timeout=1000) for img in imgsToGet)  
            reqs = await asyncio.gather(*tasks)   
            status_code_errors = [req.status_code for req in reqs if str(req.status_code)[0] != '2']
            while status_code_errors and retries_left:
                print(f'An exception occurred when gathering chap {chap} images with the status code(s) {", ".join(status_code_errors)} (will retry {retries_left} more times)')
                retries_left -= 1
                await asyncio.sleep(1)
                tasks = (client.get(f"{adress}/{img}", timeout=1000) for img in imgsToGet)  
                reqs = await asyncio.gather(*tasks)
                status_code_errors = [req.status_code for req in reqs if str(req.status_code)[0] != '2']
            
            if status_code_errors:
                print(f"Chap {chap} ignored because 5 exceptions occured")
                images = []
            else:
                images = [rep.content for rep in reqs]

        return images

    # chapter infos
    vol = c["attributes"]["volume"]
    chap = c["attributes"]["chapter"]
    fileFormat = "png" if quality else "jpg"
    id = c["id"]
    # get the title
    try:
        if not c["attributes"]["title"]:
            title = "NoTitle"
        title = format_title(c["attributes"]["title"])
    except Exception:
        title = "NoTitle"
    # check for already downloaded images in directory
    loop = asyncio.new_event_loop()
    images = loop.run_until_complete(request_images())

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

if not os.path.exists(FOLDER_PATH):
    os.makedirs(FOLDER_PATH)

print("============================================")
print(f"Mangadex Downloader/Sync script v{__VERSION__}")
print(f"By {__AUTHOR__}")
print("============================================")

# LOGIN ===========================
account = Account() 
if os.path.exists(LOGIN_PATH):
    with open(LOGIN_PATH, 'r') as file:
        content = file.read()
        if content: # token found
            print('[bold green]login tokens found...')
            tokens = json.loads(content)
            token = tokens['token']
            refresh_token = tokens['refresh_token']
            account.relogin(token, refresh_token)
        else:
            print('[bold red]Invalid token file, need to login again :')
            account.login()
else:
    print('[bold red]No login token found...')
    confirm = input("Do you want to login (y/N) ? ")
    if confirm == 'y':
        account.login()
#print(account.bearer)
# LOGIN ==========================

choices = input("[S]earch for a new manga // [U]pdate existant one // [V]erify folder state \n\t(S/U/V) ([V]erify only by default) ? "
                ).split(' ')
newSync = (1 if "S" in choices else 0)
isUpdate = (1 if "U" in choices else 0)

# User interaction
if newSync: # Search for a new manga and ask for storage choices
    print("============================================")
    print("Search type :")
    print("\t- 0 : Search engine")
    print("\t- 1 : Link to manga page")
    print("\t- 2 : Import user follows (login required)")
    print("============================================")
    choice = input("Choice (0, 1 or 2 // default is 0) : ")
    while not (choice == '0' or choice == '1' or (choice == '2' and account.check_token())):
        if choice == '2':
            print('[bold red]Not logged in')
        else:    
            print('[bold red]Choice is invalid')
        choice = input("Choice (0, 1 or 2 // default is 0) : ")

    isLink = False
    isFollows = False
    if choice == '1':
        isLink = True
        isFollows = False
    elif choice == '2':
        isLink = False
        isFollows = True
    
    if isLink: # links to page (need to get the page)
        links = input("Adress(es) to manga(s) (espaces between each adresses/ids) : ")
        ids = [link.split('/')[-2] if len(link) > 36 else link for link in links.split(' ')]
        payload = {
            "limit": 9, # numbers of results to choose from (9 by default : 10 results)
            "offset": 0,
            "ids[]": ids,
            "contentRating[]": [
                "safe",
                "suggestive",
                "erotica",
                "pornographic"
            ]
        }
    
    elif isFollows: # import of user follows
        payload = {
            'limit': 9,
            'offset': 0
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
    def search() -> dict:
        r = req.get(f"{base}/manga", params=payload)
        return r.json()
    def get_follows() -> dict:
        r = req.get(f"{base}/user/follows/manga", params=payload, headers=account.bearer)
        assert r.json()['result'] == 'ok', "follows gathering failed"
        return r.json()
    
    if isFollows:
        data = get_follows()
    else:
        data = search()
    
    with open("search.json", "w+", encoding="UTF-8") as file:
        json.dump(data, file)
    
    page = 1
    def show_titles(data, info=''):
        # clear console
        if os.name == "nt": # for Windows
            os.system('cls')
        elif os.name == "posix": # for Linux and Mac
            os.system('clear')
        # print info message if there is one
        if info:
            print('[bold red] Already at {}'.format(info))
        print("============================================")
        print("[bold blue]PAGE {}".format(page))
        print(f"Search results... (results {data['offset']+1} to {data['offset']+data['limit']})")
        if data['data']: # results found
            for i in range(len(data['data'])):
                title = data['data'][i]["attributes"]["title"]["en"] if "en" in data['data'][i]["attributes"]["title"].keys() else list(data['data'][i]["attributes"]["title"].values())[0]
                print(f"\t{i+1} : {title}")
        else: # no results found
            print("\t[bold red]No results !")
        print("============================================")
    
    # Search choice
    show_titles(data)
    mChoice = input(f"Choice (all if empty // space between values // +/- to change page): ")
    while mChoice in ('+', '-'): # page change
        info = ''
        page += 1 if mChoice == '+' else -1
        if page < 1: 
            page = 1
            info = 'first page'
        if not data['data'] and mChoice == '+':
            page -= 1
            info = 'last page'
        else:
            payload['offset'] = (page - 1) * payload['limit']
            if isFollows:
                data = get_follows()
            else:
                data = search()
        show_titles(data, info)
        mChoice = input(f"Choice (all if empty // space between values // +/- to change page): ")
    if mChoice:  
        try:
            mList = [data["data"][int(i)-1] for i in mChoice.split(" ")]
        except Exception:
            print("[bold red]Invalid choice")
            exit()
    else:
        mList = data["data"]
    
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
        if not os.path.isdir(os.path.join(FOLDER_PATH, m, "chapters")):
            os.mkdir(os.path.join(FOLDER_PATH, m, "chapters"))
        chapterList = []
        for vol in [f for f in os.listdir(os.path.join(FOLDER_PATH, m, "chapters")) if os.path.isdir(os.path.join(FOLDER_PATH, m, "chapters", f))]:
            volChapList = [chap.split('-')[1] for chap in os.listdir(os.path.join(FOLDER_PATH, m, "chapters", vol))]
            chapterList.extend(volChapList)
        chapterList = list(set(chapterList))
        chapterList.sort(key=lambda c: (float(c) if c != None and c != 'None' else 0))
        if os.path.isfile(os.path.join(FOLDER_PATH, m, "infos.json")) and open(os.path.join(FOLDER_PATH, m, "infos.json")).read():
            with open(os.path.join(FOLDER_PATH, m, "infos.json"), "r", encoding="UTF-8") as file:
                mangaInfos = json.load(file)
            if 'chapterList' not in mangaInfos.keys():
                mangaInfos['chapterList'] = []
            elif chapterList != mangaInfos['chapterList']:
                mangaInfos['chapterList'] = chapterList
            nChanges += 1
        else:
            with open(os.path.join(FOLDER_PATH, m, "chapters.json"), "r", encoding="UTF-8") as filec:
                chapters = json.load(filec)
                presentChapters = list(set([chapter["attributes"]["chapter"] for chapter in chapters]))
                presentChapters.sort(key=lambda c: (float(c) if c != None else 0))
            chapter_path = os.path.join(FOLDER_PATH, m , 'chapters')
            vol_1 = os.path.join(chapter_path, os.listdir(chapter_path)[0])
            chap_1 = os.path.join(vol_1, os.listdir(vol_1)[0])
            fSys = 1 if os.path.isfile(chap_1) else 0
            if fSys: # vol/chap-page
                if chap_1.split('.')[-1] == 'png':
                    Format = 1
                else:
                    Format = 0
            else: # vol/chap/page
                page_1 = os.path.join(chap_1, os.listdir(chap_1)[0])
                if page_1.split('.')[-1] == 'png':
                    Format = 1
                else:
                    Format = 0
            with open(os.path.join(FOLDER_PATH, m, "infos.json"), "w+", encoding="UTF-8") as file:
                mangaInfos = {
                    "fileSys" : fSys,
                    "format" : Format,
                    "id": [r['id'] for r in chapters[0]["relationships"] if r['type'] == 'manga'][0],
                    "name" : m,
                    "chapterList": presentChapters
                }
                json.dump(mangaInfos, file)
            nChanges += 1
    print('[bold blue]Verification : {} changes to infos.json files have been made'.format((nChanges if nChanges else 'No')))
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
            with open(os.path.join(FOLDER_PATH, name, "infos.json"), "w+", encoding="UTF-8") as file:
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
