"""
Function used to get all pages from a chapter (needs several infos : found in chapters.json)

When launched in main, a parser is used : 
"""

import httpx as areq # async HTTP requests
import asyncio # used to gather requests

async def getPages(imgPaths: list[str], hash: str, base: str, quality: bool):
    """
    Get all pages from imgPaths from the chapter with the hash
    (Asynchronous function : call it with "asyncio.run(getPages(imgPaths, hash, base, quality))")
    args:
        - imgPaths : list[str] : list of adresses to each page of the chapter
        - hash : str : hash linked to the chapter
        - quality : bool or equivalent (int...) to indiquate the format (True for png ; False for jpg)
        - base : str : server base : found by a GET request at endpoint /at-home/server/{idChap}

    output : list[bytes] : images in bytes to be written in image files
    """
    adress = f"{base}/data/{hash}/" if quality else f"{base}/data-saver/{hash}"
    # do the requests for each image (asynchronous)
    async with areq.AsyncClient() as client: 
        tasks = (client.get(f"{adress}/{img}", timeout=10) for img in imgPaths)  
        reqs = await asyncio.gather(*tasks)

    images = [rep.content for rep in reqs]

    return images



