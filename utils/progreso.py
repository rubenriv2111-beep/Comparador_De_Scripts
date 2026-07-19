import queue

class Progreso:
    def __init__(self, root, progressbar, label):
        self.root = root
        self.progress = progressbar
        self.label = label
        self.queue = queue.Queue()
        self.activo = True
        self._monitor()

    def actualizar(self, valor, texto=""):
        self.queue.put((valor, texto))

    def _monitor(self):
        try:
            while not self.queue.empty():
                valor, texto = self.queue.get_nowait()
                self.progress['value'] = valor
                if texto:
                    self.label.config(text=texto)
        except:
            pass
        if self.activo:
            self.root.after(100, self._monitor)

    def detener(self):
        self.activo = False