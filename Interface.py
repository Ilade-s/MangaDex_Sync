"""
Interface graphique pour utilser algo PRIM dans le cadre du probleme du voyageur de commerce
"""
from tkinter import * # GUI module
from tkinter import ttk, messagebox as msgbox # addons for GUI
from threading import Thread # Permet de faire tourner des fonctions en meme temps (async)
# Frames individuelles

__AUTHORS__ = 'Merlet Raphaël'
__VERSION__ = '0.1'

X = 300
Y = 800

class TopLevel(Tk):
    """
    Représente le client (l'interface)
    """
    def __init__(self, x=X, y=Y) -> None:
        super().__init__()
        self.version = __VERSION__
        self.authors = __AUTHORS__
        self.iconphoto(True, PhotoImage(file="assets/logo.png"))
        self.__setup_frames()

    def __setup_frames(self):
        pass

if __name__ == '__main__':
    root = TopLevel()
    root.mainloop()