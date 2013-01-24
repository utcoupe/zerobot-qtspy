import zerobot
import zmq
import threading

class SuperClient:
    def __init__(self, ctx, connect_addr="tcp://localhost:5000"):
        self.ctx = ctx
        self.clients = {}
        self.connect = connect_addr

    def call(self, service, method, args, kwargs):
        if not(service in self.clients.keys()):
            self.add_client(service)
        
        call = getattr(self.clients[service], method)
        kwargs['timeout'] = 1
        kwargs['block'] = False
        try:
            threading.Thread(target=call, args=args, kwargs=kwargs, daemon=True).run()
        except Exception as ex:
            print(ex)

    def add_client(self, service):
        if not(service in self.clients.keys()):
            client = zerobot.Client("QtSpy-%s" % service, self.connect, service, self.ctx)
            client.start(False)
            try:
                client.ping(-42, timeout=1, block=False)
            except Exception:
                print("Unable to join %s" % service)
            self.clients[service] = client

