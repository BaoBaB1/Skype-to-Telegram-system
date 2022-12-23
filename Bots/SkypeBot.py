#!/usr/bin/env python
# -*- coding: utf-8 -*-

import config
import time
import threading
from threading import Thread
from skpy import *
from Helpers import SkypeMessageParser as msgParser
from Helpers.DatabaseManager import DatabaseManager
from Helpers.IOManager import IOManager
from Bots.Bot import *

class SkypeBot(SkypeEventLoop, Bot):
    """ 
    This class represents Skype bot instance
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.attachment_requests = []
        super(SkypeBot, self).__init__(config.skype_bot_login, config.skype_bot_password)
        Bot.__init__(self, self.user.name, BotType.SKYPE_BOT, DatabaseManager(), IOManager())
        self.load_bot_commands('../skype_bot_commands.txt')
        self.commands['!about'] = self.commands['!about'].replace("{0}", str(self.name))
        self.messageParser = msgParser.SkypeMessageParser(self.userId, self.commands.keys())
        self.logger.info('Skype bot instance created')
        print('Skype bot instance created')

    def attach_file_to_message(self, msg:SkypeMsg) -> bool:
        """
        function that "attaches" user's file before message is sent in Telegram.
        Triggers only when user sends file in chat.
        @:param msg: Skype text message object
        @:return: True if file has been "attached", False otherwise
        """
        with self.lock:
            for i in range(len(self.attachment_requests)):
                if self.attachment_requests[i].sender_id == msg.userId:
                    self.attachment_requests[i].attachment = msg.fileContent  # file bytes
                    self.attachment_requests[i].attachment_name = msg.file.name
                    self.attachment_requests.remove(self.attachment_requests[i])
                    return True
            return False

    def onEvent(self, event):
        """
        function which reacts on events in chat
        @:param event: some event
        """
        if isinstance(event, SkypeNewMessageEvent) and not event.msg.userId == self.userId:
            if isinstance(event.msg, SkypeFileMsg):
                Thread(target=self.attach_file_to_message, args=(event.msg,)).start()
            elif isinstance(event.msg, SkypeTextMsg):
                # print('raw ', event.msg.raw)
                # print('plain text ' + event.msg.plain)
                Thread(target=self.react_on_message, args=(event.msg,)).start()

    # below functions defines base class Bot methods
    def react_on_message(self, msg:SkypeTextMsg):
        # new chat. new chat has always en language as default
        if self.add_new_chat(msg.chatId, msg.raw['threadtopic']):
            self.chats.chat(msg.chatId).sendMsg(self.commands['!about'], rich=True)
            self.chats.chat(msg.chatId).sendMsg(self.commands['!commands'], rich=True)
        if not self.is_message_from_group(msg.chatId):
            # if message is from private chat then we need only parse command tokens
            command = self.messageParser.get_command_token(msg.plain)
            if not command == '':
                self.answer_on_command(command, msg.chatId)
            else:
                self.answer_on_command('!commands', msg.chatId)
        else:
            parser_res = self.messageParser.parse_chat_message(msg, self.chats.chat(msg.chatId))
            if parser_res.should_react:
                if not parser_res.error_msg == '':
                    self.send_translated_message(msg.chatId, parser_res.error_msg, 'en', self.get_chat_language(msg.chatId))
                    return
                # only and if only bot hasn't been mentioned and someone sent command
                if not parser_res.command_token == '':
                    self.answer_on_command(parser_res.command_token, msg.chatId)
                    return
                else:
                    # only text
                    if not parser_res.has_attachment:
                        self.iomanager.write_message_to_file(parser_res)
                    else:
                        self.attachment_requests.append(parser_res)
                        timeout = 45
                        inform_msg = 'You have ' + str(timeout) + ' seconds to attach your file'
                        self.send_translated_message(msg.chatId, inform_msg, 'en', self.get_chat_language(msg.chatId))
                        if not wait_for_attachment(timeout, parser_res):  # if user didn't sent file, remove this request
                            self.attachment_requests.remove(parser_res)
                        self.iomanager.write_message_to_file(parser_res)
                    self.send_translated_message(msg.chatId, '{0},'.format(msg.raw['imdisplayname']) +
                                                 ' your message has been sent!', 'en', self.get_chat_language(msg.chatId))

    def send_message(self, chat_id: Union[str, int], text: str, reply_markup=None):
        self.chats.chat(chat_id).sendMsg(text, rich=True)

    def answer_on_command(self, command:str, chat_id):
        if command == '!language(uk)':
            self.update_chat_language(chat_id, 'uk')
        elif command == '!language(en)':
            self.update_chat_language(chat_id, 'en')
        elif command == '!commands':
            # don't translate commands
            self.chats.chat(chat_id).sendMsg(self.commands[command])
        elif command == '!link':
            print(self.get_chat_language(chat_id))
            self.send_translated_message(chat_id, 'This chat link: ' + str(chat_id), 'en', self.get_chat_language(chat_id))
        else:
            self.send_translated_message(chat_id, self.commands[command], 'en', self.get_chat_language(chat_id))

    def is_message_from_group(self, chat_id:str) -> bool:
        print('users in chat = ', len(self.chats[chat_id].userIds))
        return len(self.chats[chat_id].userIds) > 2

def wait_for_attachment(timeout, res, period=0.5) -> bool:
    start = time.time()
    mustend = start + timeout
    while time.time() < mustend:
        if res.attachment_name != '':
            return True
        time.sleep(period)
    return False


if __name__ == '__main__':
    bot = SkypeBot()
    bot.loop()

