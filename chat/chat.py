import logging
import os
import threading
from datetime import datetime
from time import sleep
from time import time as tim

import streamlink
from streamlink import Streamlink

import mail

import socket
import re
from emoji import demojize

class chatLogger:
    def __init__(self, targetName, Iauth, chatName, handle):
        self.targetName = targetName
        self.token = Iauth
        self.nick = chatName
        self.client = handle
        self.fetchThread: threading.Thread = None
        self.sock = socket.socket()

        if not os.path.exists("coutput"):
            os.mkdir("coutput")
        if not os.path.exists("coutput/" + self.targetName):
            os.mkdir("coutput/" + self.targetName)

    def getFN(self, time):
        return f'{self.targetName}_{time}.txt'

    def safeClose(self, io):
        try:
            if io is not None:
                io.close()
        except Exception:
            logging.exception("Safe close failed")
            pass

    def isAlive(self):
        if self.fetchThread is not None:
            if self.fetchThread.is_alive():
                return True
        return False

    # If this recorder need to start record, perform it.
    # If already in recording, do not anything.
    def requestLogging(self):
        if self.isAlive():
            return
        self.fetchThread = threading.Thread(target=self.fetchCommand)
        self.fetchThread.start()

    def point(self, cur):
        self.h = (cur - self.start) // 3600
        self.m = ((cur - self.start) % 3600) // 60
        self.s = ((cur - self.start) % 3600) % 60

        return "%02d:%02d:%02d"%(int(self.h), int(self.m), int(self.s))

    def fetchCommand(self):
        self.time = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.start = tim()
        self.channel = '#' + self.targetName

        self.sock.connect(('irc.chat.twitch.tv', 6667))
        self.sock.send(f"PASS {self.token}\n".encode('UTF-8'))
        self.sock.send(f"NICK {self.nick}\n".encode('UTF-8'))
        self.sock.send(f"JOIN {self.channel}\n".encode('UTF-8'))
        #print(self.sock.recv(2048).decode('UTF-8'))
        
        self.fn = f'coutput/{self.targetName}/' + self.getFN(self.time)
        
        while True:
            self.comment = self.sock.recv(1024).decode('UTF-8')
            try:
                self.moment = self.point(tim())
                self.talker, _, self.detail = re.search(':(.*)\!.*@.*\.tmi\.twitch\.tv PRIVMSG #(.*) :(.*)', self.comment).groups()
                self.comment =  self.moment + ' - ' + self.talker + ': ' + self.detail
            except:
                continue

            try:
                self.client.get_streams(user_login = self.targetName)
                #print(self.comment)
                
                self.text = open(self.fn, 'a', encoding='UTF-8')
                self.text.write(self.comment)
                self.text.close()
            except:
                #print('????????????????????????????????')
                break

        self.sock.close()
