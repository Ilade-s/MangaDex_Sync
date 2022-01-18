"""
Global variables used in scripts
"""
FOLDER_PATH = 'archive' # path of the folder to store the mangas folders with the images (can be either relative to the script folder or absolute)
LOGIN_PATH = 'login.json'
SIMULTANEOUS_REQUESTS = 10 # should always be under 40 (10 is best)
__VERSION__ = '1.2'
__AUTHOR__ = 'Merlet Raphaël'
def format_title(title: str) -> str:
    """format titles to be usable as filenames and foldernames"""
    return "".join(list(filter(lambda x: x not in (".", ":", '"', "?", "/", '<', '>'), title)))