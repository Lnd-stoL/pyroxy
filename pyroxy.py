
import socket
import select
import threading
import time

# Server configuration
########################################################################################################################

config_IPv6    = False
config_host    = '127.0.0.1'
config_port    = 8080
config_timeout = 60

BUFLEN  = 10000
HTTPVER = 'HTTP/1.1'


# Connections handling
########################################################################################################################

class ConnectionHandlerThread(threading.Thread):
    supportedHttpMethods = ('OPTIONS',
                            'GET',
                            'HEAD',
                            'POST',
                            'PUT',
                            'DELETE',
                            'TRACE',
                            'CONNECT')

    def __init__(self, accepted_connection):
        threading.Thread.__init__(self)

        self.accepted_connection = accepted_connection
        self.client = None
        self.client_buffer = bytes()
        self.timeout = config_timeout


    def _process_CONNECT(self, path):
        self._target = self._connect_target(path)
        self.client.send(bytes((HTTPVER+' 200 Connection established\n' + 'Proxy-agent: 1.0\n\n'), encoding="latin-1"))

        self._target_client_exchange()


    def _substitute_CDN(self, host, path):

        return False


    def _process_method(self, method, path, protocol):
        path = path[path.index(':')+3:]              # cut off protocol definition
        separator_index = path.find('/')
        host = path[:separator_index]                # split address into host and relative resource path
        path = path[separator_index:]

        if self._substitute_CDN(host, path) == True:
            return

        self._target = self._connect_target(host)    # send the HTTP response
        self._target.send(bytes('%s %s %s\n' % (method, path, protocol), encoding='latin-1'))

        self._target.send(self.client_buffer)        # send the remaining from _parse_request
        self.client_buffer = bytes()                 # and reset the buffer

        self._target_client_exchange()               # start copying from target


    def _connect_target(self, path):
        port_delim = path.find(':')
        if port_delim != -1:
            port = int(path[port_delim+1:])
            host = path[:port_delim]
        else:
            port = 80
            host = path

        (soc_family, _, _, _, address) = socket.getaddrinfo(host, port)[0]
        target = socket.socket(soc_family)
        target.connect(address)
        return target


    def _target_client_exchange(self):
        socs = [self.client, self._target]
        finished = False
        while not finished:
            (recv, _, error) = select.select(socs, [], socs, 3)
            if error:
                break
            if len(recv) == 0:
                break
            if recv:
                for in_ in recv:
                    data = in_.recv(BUFLEN)
                    if len(data) == 0:
                        finished = True
                        break
                    if in_ is self.client:
                        out = self._target
                    else:
                        out = self.client
                    if data:
                        out.send(data)
        print('Active connection threads:', len(threading.enumerate()) - 1)


    def _parse_request(self):
        request_str = ''
        while True:
            request_str += self.client.recv((BUFLEN // 8) * 2).decode('latin-1')
            end = request_str.find('\n')
            if end != -1:
                break
        print(request_str[:end])

        parsed_request = request_str[:end].split()
        self.client_buffer = bytes(request_str[end+1:], encoding='latin-1')
        return parsed_request


    def run(self):
        self.client, address = self.accepted_connection
        method, path, protocol = self._parse_request()

        if not method in self.supportedHttpMethods:
            print('Error processing request: unknown method ' + method)
            return

        if method == 'CONNECT':
            self._process_CONNECT(path)
        else:
            self._process_method(method, path, protocol)

        self.client.close()
        self._target.close()


# Start the server
########################################################################################################################

if config_IPv6 is True:               # Creating listener socket
    soc_type = socket.AF_INET6
else:
    soc_type = socket.AF_INET

soc = socket.socket(soc_type)
host_port = (config_host, config_port)
soc.bind(host_port)
soc.listen(0)
print("Proxy is up and listening %s:%d" % host_port)

while True:                          # Forever accepting incoming connections
    time.sleep(0)
    connectionThread = ConnectionHandlerThread(soc.accept())
    connectionThread.start()         # Start a thread to handle a request
