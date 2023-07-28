import glob
import logging
import os
import sys
import threading
import time

from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from pydrive2.files import GoogleDriveFile
from twitchAPI.twitch import Twitch, AuthScope
from twitchAPI.oauth import UserAuthenticator
import asyncio

import mail
from config import topic, categ, client_id, client_secret, use_gdrive, twitch_check_interval
from recorder import Recorder

twitchClient: Twitch
absoluteRec: list[Recorder] = []
conditionalRec: list[Recorder] = []
topRecorder = {}

def checkTitle(x, y):
    if x == []:
        return False
    
    for i in x:
        if i in y:
            return True

    return False

def checkCateg(x, y):
    try:
        return x[y]
    except:
        return False

def uploader(path):
    try:
        spath = path.replace("\\", "/")
        spath = spath.replace("output/", "")

        split = spath.split("/")
        id = split[0]
        fn = split[1]

        logging.info(f"Upload Quota Upload Start: {fn} on {id}")
        folder: GoogleDriveFile = None

        folder_metadata = {'title': id,
                           'mimeType': 'application/vnd.google-apps.folder',
                           "parents": [{"kind": "drive#fileLink", "id": rootDirId}]}

        query = f"title = '{id}' and '{rootDirId}' in parents and trashed = false and mimeType = 'application/vnd.google-apps.folder'"
        find = drive.ListFile({'q': query}).GetList()
        if len(find) != 0:
            folder = find[0]
        if folder is None:
            folder = drive.CreateFile(folder_metadata)
            folder.Upload()

        file = drive.CreateFile({'title': fn, "parents": [{"kind": "drive#fileLink", "id": folder['id']}]})
        file.SetContentFile(path)
        file.Upload()
        file.content.close()
        time.sleep(5)  # Wait for release file by PyDrive2 / Anti-virus / etc
        os.remove(path)
        logging.info(f"Upload Quota Upload Finished: {path}")
    except Exception:
        logging.exception(f"Upload Quota Upload Failed: {path}")
    global inUpload
    inUpload = False


def refreshFetchList(isFirst):
    L = open("absoluteList.txt", "r", encoding="utf-8").read().splitlines()
    absoluteCheck = set()
    for line in L:
        if line.strip() == "" or line.strip().startswith('#'):
            continue
        line = line.split("-")[0].strip()
        absoluteCheck.add(line)
        
    for _recorder in absoluteRec:
        if _recorder.targetName not in absoluteCheck:
            logging.info("{} removed from absoluteList".format(_recorder.targetName))
            absoluteRec.remove(_recorder)
        else:
            absoluteCheck.remove(_recorder.targetName)

    for targetName in absoluteCheck:
        if not isFirst:
            logging.info("{} added to absoluteList, check/record will started".format(targetName))
        absoluteRec.append(Recorder(targetName))

def refreshConditionalList(isFirst):
    L = open("conditionalList.txt", "r", encoding="utf-8").read().splitlines()
    conditionalCheck = set()
    for line in L:
        if line.strip() == "" or line.strip().startswith('#'):
            continue
        line = line.split("-")[0].strip()
        conditionalCheck.add(line)
        
    for _recorder in conditionalRec:
        if _recorder.targetName not in conditionalCheck:
            logging.info("{} removed from conditionalList".format(_recorder.targetName))
            conditionalRec.remove(_recorder)
        else:
            conditionalCheck.remove(_recorder.targetName)

    for targetName in conditionalCheck:
        if not isFirst:
            logging.info("{} added to conditionalList, check/record will started".format(targetName))
        conditionalRec.append(Recorder(targetName))

def get_name(recorder):
    return recorder.targetName

async def getIndiv(x):
    return twitchClient.get_streams(user_login = [x])

def selec(x):
    try:
        judge = asyncio.run(getIndiv(x))['data'][0]
    except:
        return False

    return checkTitle(topic, judge['title']) or checkCateg(categ, judge['game_name'])

if __name__ == '__main__':
    logging.basicConfig(filename='recorder.log', format='%(asctime)s %(message)s', filemode='a', level=logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logging.getLogger().addHandler(handler)

    twitchClient = Twitch(client_id, client_secret)
    
    target_scope = [AuthScope.USER_READ_FOLLOWS]
    auth = UserAuthenticator(twitchClient, target_scope, force_verify = False)
    
    tok, ref_tok = auth.authenticate()
    twitchClient.set_user_authentication(tok, target_scope, ref_tok)

    if use_gdrive:
        gauth = GoogleAuth()
        gauth.settings['get_refresh_token'] = True
        # Create local webserver and auto handles authentication.
        gauth.LoadCredentialsFile("token.key")
        if gauth.credentials is None:
            # Authenticate if they're not there
            gauth.LocalWebserverAuth()
        elif gauth.access_token_expired:
            # Refresh them if expired
            gauth.Refresh()
        else:
            # Initialize the saved creds
            gauth.Authorize()
        # Save the current credentials to a file
        gauth.SaveCredentialsFile("token.key")

        drive = GoogleDrive(gauth)

        fd = open('rootDir.id', 'r')
        rootDirId = fd.readline().strip()
        fd.close()

        uploadThread = None
    inUpload = False
    already = []

    refreshFetchList(True)
    refreshConditionalList(True)
        
    while True:
        refreshFetchList(False)
        refreshConditionalList(False)

        absolute = list(map(get_name, absoluteRec))
        conditional = list(filter(selec, map(get_name, conditionalRec)))

        total = absolute + conditional
        totalRec = absoluteRec + conditionalRec
        recorder: Recorder

        os.system('cls')
        if total:
            onlineCount = 0
            for i in range(0, len(total), 100):
                try:
                    streams = twitchClient.get_streams(user_login = total[i:i + 100], first=100)
                    onlineCount += len(streams['data'])
                    for stream in streams['data']:
                        for recorder in totalRec:
                            if recorder.targetName == stream['user_login']:
                                recorder.requestRecord()
                        print(f"{stream['user_login']}: Live")
                except:
                    pass
            print(f"Checked: {onlineCount}/{len(totalRec)} is Online.")
        print()                

        time.sleep(twitch_check_interval)

        if use_gdrive and not inUpload:
            finishList = glob.glob(f'output/**/Fin_*.mp4', recursive=True)
            if len(finishList) == 0:
                pass
            else:
                inUpload = True
                uploadThread = threading.Thread(target=uploader, args=(finishList[0] + "",))
                uploadThread.start()
