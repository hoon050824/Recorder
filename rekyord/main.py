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
from config import topic, client_id, client_secret, use_gdrive, twitch_check_interval
from recorder import Recorder

twitchClient: Twitch
recorders: list[Recorder] = []
topRecorder = {}

def check(x, y):
    for i in x:
        if i in y:
            return True

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
    L = open("fetchList.txt", "r", encoding="utf-8").read().splitlines()
    fetchCheck = set()
    for line in L:
        if line.strip() == "" or line.strip().startswith('#'):
            continue
        line = line.split("-")[0].strip()
        fetchCheck.add(line)
        
    for _recorder in recorders:
        if not _recorder.targetName in fetchCheck:
            logging.info("{} removed from list".format(_recorder.targetName))
            recorders.remove(_recorder)
        else:
            fetchCheck.remove(_recorder.targetName)

    for targetName in fetchCheck:
        if not isFirst:
            logging.info("{} added to list, check/record will started".format(targetName))
        recorders.append(Recorder(targetName))

def get_name(recorder):
    return recorder.targetName

async def followed():
    #print(twitchClient.get_users()['data'][0]['id'])
    name = twitchClient.get_users()['data'][0]['id']

    #print([i['user_name'] for i in twitchClient.get_followed_streams(name)['data'] if check(topic, i['title'])])
    #print([i['user_login'] for i in twitchClient.get_followed_streams(name)['data'] if check(topic, i['title'])])
    List = [i['user_login'] for i in twitchClient.get_followed_streams(name)['data'] if check(topic, i['title'])]

    return List

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

    refreshFetchList(True)
    already = []
        
    while True:
        refreshFetchList(False)

        intended = list(map(get_name, recorders))
        keyword = list(asyncio.run(followed()))
        recorder: Recorder

        #print(intended)
        #print(keyword)

        os.system('cls')
        if intended:
            onlineCount = 0
            for i in range(0, len(intended), 100):
                try:
                    streams = twitchClient.get_streams(user_login = intended[i:i + 100], first=100)
                    onlineCount += len(streams['data'])
                    for stream in streams['data']:
                        for recorder in recorders:
                            if recorder.targetName == stream['user_login']:
                                recorder.requestRecord()
                        print(f"{stream['user_login']}: Live")
                except:
                    pass
            print(f"Checked: {onlineCount}/{len(intended)} is Online.")
        print()

        
        if keyword:
            for i in keyword:
                if i not in already:
                    recorder = Recorder(i)
                    recorder.requestRecord()
                    already.append(i)
                print(f"{i}: Keyword")
            print(f"{len(keyword)} Broadcasts contain the Keyword.")
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
