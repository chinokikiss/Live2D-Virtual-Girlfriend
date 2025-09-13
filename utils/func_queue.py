import threading
from queue import Queue

class FuncQueue:
    def __init__(self, start_callback=None, stop_callback=None, max_t=1):
        self.q = Queue()
        self.t = []
        self.max_t = max_t
        self.start_callback = start_callback
        self.stop_callback = stop_callback
    
    def process(self):
        if self.start_callback:
            self.start_callback()
        
        while not self.q.empty():
            func, args = self.q.get()
            func(*args)
            
        if self.stop_callback:
            self.stop_callback()
    
    def add(self, func, args=()):
        self.q.put([func, args])

        for i in range(len(self.t)-1, -1, -1):
            if not self.t[i].is_alive():
                self.t.pop(i)

        if len(self.t) < self.max_t:
            t = threading.Thread(target=self.process, daemon=True)
            self.t.append(t)
            t.start()