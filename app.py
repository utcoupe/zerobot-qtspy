#!/usr/bin/env python3

import sys
import optparse

import time
import json
import re
from html.entities import codepoint2name as entities

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from client import SuperClient

usage = "usage: %prog [options]"
parser = optparse.OptionParser(usage,version="%prog 0.0.1")
parser.add_option("-c", "--connect",
    action="store", dest="connect", default="tcp://localhost:5002",
    help="connect. ex : tcp://localhost:5002")

htmlentities = lambda x : ''.join('&%s;' % entities[ord(c)] if ord(c) in entities else c for c in str(x))

class QtSpyWindow(QMainWindow):
    def __init__(self, connect_addr):
        super(MyWindow, self).__init__()
        
        self.ctx = zmq.Context()
        self.receiver = self.ctx.socket(zmq.SUB)
        self.receiver.connect(connect_addr)
        self.receiver.setsockopt(zmq.SUBSCRIBE, ''.encode())
        fd = self.receiver.getsockopt(zmq.FD)
        
        self.notifier = QSocketNotifier(fd, QSocketNotifier.Read, self)
        self.notifier.activated.connect(self.process_stuff)
        
        self.requests = {}
        
        self.services_views = {}
        self.services = SuperClient(ctx)
        
        self.__init_gui()

    def __init_gui(self):
        self.resize(550, 700)
    
        layout = QHBoxLayout()
        layout2 = QVBoxLayout()
        layout3 = QVBoxLayout()
        
        widget = QWidget(self)
        widget.setLayout(layout)
        self.setCentralWidget(widget)
        
        layout.addLayout(layout3)
        
        self.tabs = QTabWidget(self)
        layout3.addWidget(self.tabs)
        
        self.history = []
        self.current_history_index = -1
        
        self.console = QLineEdit(self)
        self.console.setText('service.method(arg1, arg2, arg3=3)')
        self.console.returnPressed.connect(self.on_console_send)
        self.console.installEventFilter(self)
        self.console.setFocus()
        layout3.addWidget(self.console)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            order = None
            if event.key() == Qt.Key_Up:
                order = self.get_history_up()
            elif event.key() == Qt.Key_Down:
                order = self.get_history_down()
            if not(order is None):
                self.console.setText(order)
                return True
        return obj.eventFilter(obj, event)

    def get_textedit(self, nom):
        if nom in self.services_views.keys():
            return self.services_views[nom]
        else:
            text = QTextBrowser(None)
            self.services_views[nom] = text
            self.tabs.addTab(text, nom.decode())
            return text

    def on_console_send(self, *args):
        order = self.console.text()
        #Le but est de récupérer le nom du service, la méthode a appeler et les arguments
        #on découpe d'abord en trois morceaux avec un regex
        res = re.findall(r"([a-zA-Z_\-]*\.)?([a-zA-Z0-9\-_]+) ?\((.*)\)", order)
        service = res[0][0]
        if service == '':
            service = self.tabs.tabText(self.tabs.currentIndex()) # TODO
        else:
            service = service[:-1]
        method = res[0][1]
        
        #Pour récupérer les arguments comme objets python on va utiliser eval
        #en remplaçant le dict 'locals' par un contenant seulement la fonctione 'identity'
        arguments = "a(%s)" % res[0][2]
        def identity(*args, **kwargs):
            return args, kwargs
        args, kwargs = eval(arguments,{'__builtin__':{}},{'a':identity})
        
        #Appel de la fonction, reset de la console et historique
        self.services.call(service, method, args, kwargs)
        self.console.setText('')
        self.add_to_history(order)
        
    def add_to_history(self, order):
        self.history.append(order)
        self.current_history_index = len(self.history) - 1

    def get_history_up(self):
        if self.current_history_index >= 0:
            order = self.history[self.current_history_index]
            self.current_history_index -= 1
            return order
        return None

    def get_history_down(self):
        if self.current_history_index+2 == len(self.history):
            self.current_history_index += 1
            return ''
        elif self.current_history_index+2 < len(self.history):
            self.current_history_index += 1
            return self.history[self.current_history_index+1]
        return None

    def process_stuff(self, sock):
        while self.receiver.getsockopt(zmq.EVENTS) & zmq.POLLIN:
            message = self.receiver.recv_multipart()
            from_, to, msg = message
            msg = json.loads(msg.decode())
            
            if 'data' in msg.keys() or 'error' in msg.keys():
                new_text = "<br/>"
                
                ans, req = msg, self.requests[msg["uid"]]
                new_text += "<i style='font-size: small'>%s</i> <b>%s : %s.%s(" % (time.strftime("%H:%M:%S", time.localtime()) ,to.decode(), from_.decode(), req["fct"])
                for arg in req["args"]:
                    new_text += "%s, " % arg
                for arg in req["kwargs"].items():
                    new_text += "%s=%s, " % arg
                if req["args"] or req["kwargs"]:
                    new_text = new_text[:-2]
                new_text += ")</b><br/>"
                if ans["error"] is None:
                    new_text += "<span style='color: green;'>%s</span>" % (htmlentities(ans["data"]))
                else:
                    new_text += "<span style='color: red;'>Error : %s<br/>Traceback : %s</span>" % (htmlentities(ans["error"]["error"]),
                                                                                                    htmlentities(ans["error"]["tb"]))
                
                self.get_textedit(from_).append(new_text)
                del self.requests[ans["uid"]]
            else:
                self.requests[msg["uid"]] = (msg)

        return True

if __name__ == '__main__':
    (options, _args) = parser.parse_args()
    app = QApplication(sys.argv)
    win = QtSpyWindow(options.connect)
    win.show()
    app.exec_()
