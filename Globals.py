"""
Global variables used in scripts
"""
FOLDER_PATH = 'archive' # name of the folder to store the mangas folders with the images
SIMULTANEOUS_REQUESTS = 10 # should always be under 40 (10 is best)
__VERSION__ = '1.1'
__AUTHOR__ = 'Merlet Raphaël'
def format_title(title: str) -> str:
    """format titles to be usable as filenames and foldernames"""
    return "".join(list(filter(lambda x: x not in (".", ":", '"', "?", "/", '<', '>'), title)))