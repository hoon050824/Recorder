import logging
import os
import threading
from datetime import datetime
from time import sleep

import streamlink
from streamlink import Streamlink

import mail


class Recorder:
    def __init__(self, targetName, aka):
        self.targetName = targetName
        self.aka = aka
        self.fetchThread: threading.Thread = None

        if not os.path.exists("output"):
            os.mkdir("output")
        if not os.path.exists("output/" + self.aka):
            os.mkdir("output/" + self.aka)

    def getFN(self, time):
        return f'{self.targetName}_{time}.mp4'

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
    def requestRecord(self):
        if self.isAlive():
            return
        self.fetchThread = threading.Thread(target=self.fetchCommand)
        self.fetchThread.start()

    def fetchCommand(self):
        time = datetime.now().strftime("%Y%m%d_%H%M%S")
        logging.info(f"{self.targetName}'s stream: Started at {time}")
        mail.send(f'Start Recording for {self.targetName}')
        session = Streamlink()
        session.set_option('hls-live-restart', True)
        session.set_plugin_option('twitch', 'disable-ads', True)

        if os.path.exists('twitch.token'):
            logging.info(f"{self.targetName}'s stream: Using exist twitch oauth token")
            with open('twitch.token', 'r', encoding='utf8') as f:
                token = f.read()
            session.set_plugin_option('twitch', 'api-header', {'Authorization': f'OAuth {token.strip()}'})

        streams = session.streams(f"http://twitch.tv/{self.targetName}")
        if len(streams) == 0:
            mail.send(f'Invalid Token? for {self.targetName}')
            logging.error(f"{self.targetName}'s stream: Stream list is empty, retry without api-header")
            session.set_plugin_option('twitch', 'api-header', {})
            streams = session.streams(f"http://twitch.tv/{self.targetName}")
        stream = streams['best']
        stream = stream.open()

        fn = f'output/{self.aka}/' + self.getFN(time)
        file = open(fn, 'wb')

        recoverTries = 0
        waitCount = 0

        while True:
            if recoverTries > 10 or waitCount > 20:
                break

            try:
                readed = stream.read(1024 * 256)
                if len(readed) == 0:
                    sleep(0.5)
                    waitCount += 1
                    continue
                file.write(readed)

            except Exception:
                logging.exception(f"{self.targetName}'s stream: Exception on processing")
                mail.send(f'Error raised on Recording for {self.targetName}')
                break

        self.safeClose(stream)
        self.safeClose(file)
        logging.info(f"{self.targetName}'s stream: fetchCommand is Done.")
        mail.send(f'Finished Recording for {self.targetName}')
        self.fetchThread = None

        os.rename(fn, f'output/{self.targetName}/Fin_' + self.getFN(time))

        try:
            already.remove(self.targetName)
        except:
            pass
