#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from ui.interfaz import App
import tkinter as tk

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
#Get-ChildItem -Recurse -Directory -Filter __pycache__ | Remove-Item -Recurse -Force