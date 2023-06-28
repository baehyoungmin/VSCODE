import lupa
from lupa import LuaRuntime
from threading import Thread
from threading import Timer
import queue
import json
import requests_async
import requests
from requests import exceptions
import asyncio
import time, sys
from datetime import datetime
import fibapi

def httpCall(method, url, options, data, local):
    ''' http called from lua, async-wait if we call our own api (local, Fast API) '''
    headers = options['headers']
    req = requests if not local else requests_async.ASGISession(fibapi.app)
    match method:
        case 'GET':
            res = req.get(url, headers = headers)
        case 'PUT':
            res = req.put(url, headers = headers, data = data)
        case 'POST':
            res = req.post(url, headers = headers, data = data)
        case 'DELETE':
            res = req.delete(url, headers = headers, data = data)
    res = asyncio.run(res) if local else res
    return res.status_code, res.text , res.headers

def httpCallAsync(fibemu, method, url, options, data, local):
    ''' http call in separate thread and post back to lua '''
    def runner():
        status, text, headers = httpCall(method, url, options, data, local)
        headers = dict(headers)
        fibemu.postEvent(
            {"_unserializable":options,"type":"httpResponse","status":status,"data":text,"headers":headers}
        )
    rthread = Thread(target=runner, args=())
    rthread.start()

def convertLuaTable(obj):
    if lupa.lua_type(obj) == 'table':
        if obj[1] and not obj['_dict']:
            b = [convertLuaTable(v) for k,v in obj.items()]
            return b
        else:
            d = dict()
            for k,v in obj.items():
                if k != '_dict':
                    d[k] = convertLuaTable(v)
            return d
    else:
        return obj

def tofun(fun):
    a = type(fun)
    return fun[1] if type(fun) == tuple else fun

class FibaroEnvironment:
    def __init__(self, config):
        self.config = config
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.queue = queue.Queue()

    def postEvent(self,event): # called from another thread
        self.queue.put(event)  # safely qeued for lua thread

    def getUI(self,id): # called from another thread
        pass
    
    def remoteCall(self,method,*args): # called from another thread
        try:
            fun = self.QA.fun              # unsafe call to lua function in other thread
            fun = tofun(fun)[method]
            res,code = tofun(fun)(*args)
            res = convertLuaTable(res)
        except Exception as e:
            print(f"Remote Call Error: {e}",file=sys.stderr)
        return res,code or 501

    def refreshStates(self,start,url,options):
        if self.config.get('local'):
            return
        options = convertLuaTable(options)
        def refreshRunner():
            last,retries = 0,0
            while True:
                try:
                    nurl = url + str(last)
                    resp = requests.get(nurl, headers = options['headers'])
                    if resp.status_code == 200:
                        data = resp.json()
                        last = data['last'] if data['last'] else last
                        if data.get('events'):
                            for event in data['events']:
                                self.postEvent({"type":"refreshStates","event":event})
                except exceptions.ConnectionError as e:
                    retries += 1
                    if retries > 5:
                        return
                except Exception as e:
                    print(f"Error: {e} {nurl}")
                    
        self.rthread = Thread(target=refreshRunner, args=())
        self.rthread.start()

    def run(self):

        def runner():
            config = self.config
            globals = self.lua.globals()
            self.events = list()
            hooks = {
                'clock':time.time,
                'http':httpCall,
                'httpAsync':lambda method, url, options, data, local: httpCallAsync(self, method, url, options, data, local),
                'refreshStates':lambda start, url, options: self.refreshStates(start,url,options)
            }
            config['hooks'] = hooks
            emulator = config['path'] + "lua/" + config['emulator']
            f = self.lua.eval(f'function(config) loadfile("{emulator}")(config) end')
            f(self.lua.table_from(config))
            QA = globals.QA
            self.DIR =globals.DIR
            self.QA = QA
            self.QA.addEvent = lambda e: self.events.append(json.loads(e))
            if config['init']:
                QA.runFile(config['init'])
            if config['file1']:
                self.postEvent({"type":"installQA","file":config['file1']})
            if config['file2']:
                self.postEvent({"type":"installQA","file":config['file2']})
            if config['file2']:
                self.postEvent({"type":"installQA","file":config['file3']})
            while True: # main loop, repeatadly call QA.dispatcher with events
                delay = QA.dispatcher()
                # print(f"event: {delay}s", end='')
                try:
                    event = self.queue.get(block=True, timeout=delay)
                except queue.Empty:
                    event = None
                # print(f", {self.event}")
                if event:
                    try:
                        u = None
                        if event.get('_unserializable'):
                            u = event['_unserializable']
                            del event['_unserializable']
                        QA.onEvent(json.dumps(event),u)
                    except Exception as e:
                        print(f"onEvent Error: {e}")

        self.thread = Thread(target=runner, args=())
        self.thread.start()
