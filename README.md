# MangaDex_Sync
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
