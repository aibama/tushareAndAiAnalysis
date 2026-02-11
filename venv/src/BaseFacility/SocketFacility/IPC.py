import io
import re
import select
import socket
import sys
import threading
import GlobalVariable.SocketMessage.TaskMessage as task


class IPC(threading.Thread):

    def __init__(self, line_filter = None):
        threading.Thread.__init__(self)
        self.daemon = True
        self.lock = threading.Lock()
        self.event = threading.Event()
        self.event.clear()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.recv_buffer_size = 8192
        self.buffer = io.StringIO
        if(line_filter == None):
            self.line_filter = lambda x: x
        else:
            self.line_filter = line_filter


    def run(self):
        self.sock.connect(("localhost", 32000))
        data = True
        while data:
            try:
                data = self.sock.recv(self.recv_buffer_size)
            except socket.error as e:
                print(e)
                self.sock.close()
                break

            self.lock.acquire()
            self.buffer.write(data)
            self.lock.release()
            # 线程释放锁状态
            self.event.set()

    def readlines(self):
        self.lock.acquire()

        self.buffer.seek(0)
        raw_lines = self.buffer.readlines()
        self.buffer.truncate(0)

        self.lock.release()

        lines = map(self.line_filter, raw_lines)
        return lines

    def send(self,*args, **kwargs):
        str = "{} {}"
        self.sock.send(str.format(*args, **kwargs))

if __name__== "__main__":
    ipc = IPC()
    ipc.send()

