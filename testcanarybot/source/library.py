import asyncio
import importlib
import json
import os
import six
import threading
import traceback

from typing import Union
from types import MethodType

from . import objects
from . import exceptions
from .values import global_expressions, Pages
from .enums import events

class _assets:
    def __init__(self):
        self.path = os.getcwd() + '\\assets\\'

    def __call__(self, *args, **kwargs):
        args = list(args)
        if len(args) > 0:
            args[0] = self.path + args[0]
        
        elif 'file' in kwargs:
            kwargs['file'] = self.path + kwargs['file']
        
        return open(*args, **kwargs)

    def __exit__(self, exc_type, exc_value, traceback):
        pass

assets = _assets()
tools_test = objects.tools()
package_test = objects.package(**{'type': events.message_new, 'items': ['test']})

class handler(threading.Thread):
    processing = False

    def __init__(self, library, handler_id):
        threading.Thread.__init__(self)
        self.daemon = True
        self.handler_id = handler_id

        self.library = library
        self.packages = []


    def run(self):
        self.setName(f"handler_{self.handler_id}")
        self.library.tools.system_message(f"{self.getName()} is started", module = "package_handler")

        self.all_messages = self.library.tools.values.ALL_MESSAGES.value
        self.add_mentions = self.library.tools.values.MENTIONS.value
        self.mentions = self.library.tools.mentions

        self.thread_loop = asyncio.new_event_loop()
        self.thread_loop.set_exception_handler(self.exception_handler)
        asyncio.set_event_loop(self.thread_loop)
        self.library.tools.http.create_session(self)

        self.thread_loop.run_forever()

    def exception_handler(self, loop, context):
        try:
            raise context['exception']

        except Exception as e:
            print(type(context['exception']).__name__)
            print(e)

    def create_task(self, package):
        if package.type == events.message_new or package.type in self.library.handlers['events']:
            asyncio.run_coroutine_threadsafe(self.resolver(package), self.thread_loop)


    async def resolver(self, package):
        if package.type == events.message_new:
            await asyncio.sleep(0.00001)

            if hasattr(package, 'action'): 
                package.params.action = True

            elif hasattr(package, 'payload'): 
                package.params.payload = True
                package.payload = json.loads(package.params)
            
            elif package.text != '':
                message = package.text.split()
                print(message)
                print(self.mentions)
                if (message[0].lower() in self.mentions) or (message[0][:-1].lower() in self.mentions):
                    if len(message) > 1:
                        message.pop(0)
                        package.params.command = True
                else:
                    package.params.command = False

                package = await self.findMentions(package, message)

            elif len(package.attachments) > 0: 
                package.params.attachments = True

            await self.handler(package)
            
        else:
            await self.handler(package)


    async def findMentions(self, package: objects.package, message: str) -> objects.package:
        for count in range(len(message)):
            if message[count][0] == '[' and message[count].count('|') == 1:
                if message[count].count(']') > 0:
                    mention = self.library.tools.parse_mention(
                            message[count][message[count].rfind('[') + 1:message[count].find(']')]
                            )
                    package.params.mentions.append(mention)
                    package.items.append(
                        mention
                        )
                else:
                    for j in range(count, len(message)):
                        if message[j].count(']') > 0:
                            last_string, message[j] = message[j][0:message[j].find(']')], message[j][message[j].find(']') + 1:]
                            mention = self.library.tools.parse_mention(" ".join([*message[count:j], last_string])[1:])
                            package.items.append(mention)
                            package.params.mentions.append(mention)
                            count = j
                            break
            else:
                package.items.append(message[count])
            count += 1
        return package
            

    async def handler(self, package: objects.package):
        package.items.append(self.library.tools.values.ENDLINE)
        try:
            if package.type == events.message_new:
                test = objects.WaitReply(package)
                if test in self.library.tools.waiting_replies:
                    self.library.tools.waiting_replies[test] = package

                elif package.params.command and len(package.items) > 0 and package.items[0] in self.library.handlers['priority'].keys():
                    for i in self.library.handlers['priority'][package.items[0]]:
                        module = self.library.modules[i.__module__]
                        
                        self.thread_loop.create_task(i(module, self.library.tools, package))
                        await asyncio.sleep(0.00001)

                elif self.library.void_react:
                    if self.all_messages or package.params.command:
                        for i in self.library.handlers['void']:
                            module = self.library.modules[i.__module__]

                            self.thread_loop.create_task(i(module, self.library.tools, package))
                            await asyncio.sleep(0.00001)

            elif package.type in self.library.handlers['events'].keys():
                for i in self.library.handlers['events'][package.type]:
                    module = self.library.modules[i.__module__]
                    self.thread_loop.create_task(i(module, self.library.tools, package))

                    await asyncio.sleep(0.00001)
        except Exception as e:
            self.library.tools.system_message(module = "exception_handler", write = e)


class databases:
    def __init__(self, names: list):
        self.upload(names)


    def check(self, name):
        response = [*self.__dbs.keys(), 
                *[i.directory for i in self.__dbs.values()]]

        return name in response 


    def upload(self, names):
        self.__dbs = {}
        self.add(names)


    def get(self, name):
        check = type(name)
        if check == tuple:
            if not self.check(name[0]):
                raise exceptions.DBError("This DB does not exist")

            else:
                return self.__dbs[name[1]]

        elif check == str:
            if not self.check(name):
                raise exceptions.DBError("This DB does not exist")

            else:
                return self.__dbs[name]



    def add(self, names): 
        check = type(names)

        if check == list:
            for name in names:
                if self.check(name[0]):
                    raise exceptions.DBError("This DB already exists")

                else:
                    self.__dbs[name[0]] = objects.database(name[1])

        elif check == tuple:
            if self.check(names[0]):
                raise exceptions.DBError("This DB already exists")

            else:
                self.__dbs[names[0]] = objects.database(names[1])

        elif check == str:
            if self.check(names):
                raise exceptions.DBError("This DB already exists")

            else:
                self.__dbs[names] = objects.database(names)
        
        else:
            raise exceptions.DBError("Incorrect type of 'names'")


class library:
    modules = {}
    handlers = {
        'void': [], # [handler1, handler2]
        'priority': {}, # {'test', 'hello', 'world'}: [handler1, handler2, ...]
        'events': {} # event.abstract_event: [handler1, handler2]
    }

    def __init__(self, v, group_id, api, http, log):
        self.supp_v = v
        self.tools = tools(group_id, api, http, log)
        self.void_react = False
        self.commands = []


    def getPriority(self, command):
        return self.handlers['priority'][command]

    def getVoid(self):
        return self.handlers['void']
            

    def upload(self, isReload = False, loop = asyncio.get_event_loop()):
        self.modules = {}
        if 'library' in os.listdir(os.getcwd()):
            self.tools.system_message(str(self.tools.values.LIBRARY_GET), module = "library.uploader")
            
            listdir = os.listdir(os.getcwd() + '\\library\\')
            listdir.remove("__pycache__")
            if len(listdir) == 0:
                raise exceptions.LibraryError(
                    self.tools.values.SESSION_LIBRARY_ERROR)
            init_async(
                    asyncio.wait(
                        [
                            loop.create_task(self.upload_handler(module)) for module in listdir
                        ]
                    ), loop = loop
                )
            self.tools.system_message(
                "Supporting event types: {event_types}".format(
                    event_types = "\n".join(["", "\t\tevents.message_new", *["\t\t" + str(i) for i in self.handlers['events'].keys()], ""])
                ), module = "library.uploader", newline = True)
    

    async def upload_handler(self, module_name):
        module_name = "library." + (module_name[:-3] if module_name.endswith('.py') else module_name + '.main')
        module = importlib.import_module(module_name)

        if hasattr(module, 'Main'):
            moduleObj = module.Main()
            moduleObj.module_name = module_name

            if moduleObj.v in self.supp_v:
                pass
            else:
                return self.tools.system_message(self.tools.values.MODULE_FAILED_VERSION.value.format(
                    module = module_name), module = "library.uploader")
                    
            if hasattr(moduleObj, "start"):
                await moduleObj.start(self.tools)
                
            if not issubclass(type(moduleObj), objects.libraryModule):
                return self.tools.system_message(self.tools.values.MODULE_FAILED_SUBCLASS.value.format(
                    module = module_name), module = "library.uploader")

        else:
            return self.tools.system_message(self.tools.values.MODULE_FAILED_BROKEN.value.format(
                module = module_name), module = "library.uploader")
                
        dir_module = dir(moduleObj)
        dir_obj = dir(objects.libraryModule)
        coros = set(dir_module) - set(dir_obj)
        for coro_name in coros:
            coro = getattr(moduleObj, coro_name)

            if coro_name not in ['start', 'priority', 'void', 'event'] and callable(coro):
                try:
                    await coro(self.tools, package_test)

                except:
                    pass

        message = self.tools.values.MODULE_INIT.value.format(
            module = module_name)

        if len(moduleObj.commands) == 0 and len(moduleObj.event_handlers.keys()) == 0 and not moduleObj.void_react:
            return self.tools.system_message(self.tools.values.MODULE_FAILED_HANDLERS.value.format(
                module = module_name), module = "library.uploader")
        
        if len(moduleObj.commands) > 0:
            message += self.tools.values.MODULE_INIT_PRIORITY.value.format(count = len(moduleObj.commands))

            for i in moduleObj.handler_dict.values():
                for j in i['commands']:
                    if j not in self.handlers['priority']:
                        self.handlers['priority'][j] = []

                    self.handlers['priority'][j].append(i['handler'])

        if len(moduleObj.event_handlers.keys()) > 0:
            for event in moduleObj.event_handlers.keys():
                message += self.tools.values.MODULE_INIT_EVENTS.value.format(event = str(event))
                if not event in self.handlers['events']:
                    self.handlers['events'][event] = []

                self.handlers['events'][event].extend(moduleObj.event_handlers[event])
        

        if moduleObj.void_react:
            self.handlers['void'].append(moduleObj.void_react)
            self.void_react = True
            message += self.tools.values.MODULE_INIT_VOID.value

        self.modules[module_name] = moduleObj
        return self.tools.system_message(write = message, module = "library.uploader")


    def getCompactible(self, event):
        if event in self.handlers['events'].keys():
            return self.handlers['events'][event]
        else:
            return []


class tools(objects.tools):
    __module = "system_message"
    __db = databases(("system", "system.db"))

    def __init__(self, group_id, api, http, log):
        self.group_id = group_id
        self.api = api
        self.assets = assets
        self.http = http
        self.log = log
        self.waiting_replies = {}
        
        init_async(self.__setShort())

        self.group_mention = f'[club{self.group_id}|@{self.group_address}]'
        self.mentions = [self.group_mention]

        self.get = self.__db.get
        self.values = global_expressions()

    
    async def __setShort(self):
        res = await self.api.groups.getById(group_id=self.group_id)
        self.group_address = res[0].screen_name
        return
    

    async def wait_reply(self, package):
        wait = objects.WaitReply(package)
        self.waiting_replies[wait] = False

        while True:
            if self.waiting_replies[wait]: 
                return self.waiting_replies.pop(wait)
            
            await asyncio.sleep(0)


    def system_message(self, *args, write = None, module = None, newline = False):
        if not module: module = self.__module
        if not write: write = " ".join([str(i) for i in list(args)])
        
        response = f'@{self.group_address}.{module}: {write}'

        if self.log.closed:
            self.log = assets("log.txt", "a+", encoding="utf-8")

        newline_res = "\n" if newline else ""
        print(newline_res + response)

        response = f'{self.getDateTime()} {response}'
        print(newline_res + response, file=self.log)

        self.log.flush()

    
    def makepages(self, obj:list, page_lenght: int = 5, listitem: bool = False):
        listitem_symb = self.values.LISTITEM if listitem else str()
        return Pages(obj, page_lenght, listitem_symb)


    def add(self, db_name):
        self.__db.add((db_name, self.assets.path + db_name))


    async def getMention(self, page_id: int, name_case = "nom"):
        if name_case == 'link':
            if page_id > 0:
                return f'[id{page_id}|@id{page_id}]'

            elif page_id == self.group_id:
                return self.group_mention

            else:
                test = await self.api.groups.getById(group_id = -page_id)
                return f'[club{-page_id}|@{test[0].screen_name}]'
        
        else:
            if page_id > 0:
                request = await self.api.users.get(
                    user_ids = page_id, 
                    name_case = name_case
                    )
                first_name = request[0].first_name
                
                return f'[id{page_id}|{first_name}]'
            
            elif page_id == self.group_id:
                return self.mentions_self[name_case]
            
            else:
                request = await self.api.groups.getById(
                    group_id = -page_id
                    )
                name = request[0].name
                
                return f'[club{-page_id}|{name}]' 


    async def getManagers(self, group_id = None):
        if not group_id:
            group_id = self.group_id

        elif not isinstance(group_id, int):
            raise TypeError('Group ID should be integer')

        lis = await self.api.groups.getMembers(group_id = group_id, sort = 'id_asc', filter='managers')
        return [i.id for i in lis.items if i.role in ['administrator', 'creator', 'moderator']]


    async def isManager(self, from_id: int, group_id = None):
        if not group_id:
            group_id = self.group_id
            
        elif not isinstance(group_id, int):
            raise TypeError('Group ID should be integer')

        return from_id in await self.getManagers(group_id)


    async def getChatManagers(self, peer_id: int):
        res = await self.api.messages.getConversationsById(peer_ids = peer_id)
        res = res.items[0].chat_settings
        response = [*res.admin_ids, res.owner_id]
        return response
        

    def isChatManager(self, from_id, peer_id: int):
        return from_id in self.getChatManagers(peer_id)


    async def getMembers(self, peer_id: int):
        response = await self.api.messages.getConversationMembers(peer_id = peer_id)
        return [i['member_id'] for i in response['items']]


    async def isMember(self, from_id: int, peer_id: int):
        return from_id in await self.getMembers(peer_id)


class api:
    __slots__ = ('http', '_method', '_string')

    def __init__(self, http, method, string = None):
        self.http = http
        self._method = method    
        self._string = string


    def __getattr__(self, method):
        if '_' in method:
            m = method.split('_')
            method = m[0] + ''.join(i.title() for i in m[1:])

        self._string = self._string + "." if self._string else ""

        return api(
            self.http, self._method,
            (self._string if self._method else '') + method
        )

    async def __call__(self, **kwargs) -> Union[objects.data, dict]:
        for k, v in six.iteritems(kwargs):
            if isinstance(v, (list, tuple)):
                kwargs[k] = ','.join(str(x) for x in v)

        result = await self._method(self._string, kwargs)
        if isinstance(result, list):
            return [
                objects.data(**i) for i in result
            ]
        
        elif isinstance(result, dict):
            return objects.data(**result)

        else:
            return result


def init_async(coro: asyncio.coroutine, loop = asyncio.get_event_loop()):
    if loop.is_running():
        raise exceptions.LoopStateError("This event loop is currently running")

    else:
        return loop.run_until_complete(coro)
