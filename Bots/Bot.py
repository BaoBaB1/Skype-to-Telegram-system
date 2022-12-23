import json
import logging
from deep_translator import GoogleTranslator
from telebot.types import Message
from typing import Union
from skpy import SkypeTextMsg
from enum import Enum

class BotChat:
    """
    This class represents chat in which bot is present
    """
    def __init__(self, chat_id: Union[str, int], language: str, chat_name: str):
        """
        @:param chat_id: chat id
        @:param language: chat language
        @:param chat_name: chat name
        """
        self.chat_id: Union[str, int] = chat_id
        self.language = language
        self.name = chat_name

class BotType(Enum):
    """
    This class represents supported types of bots
    """
    SKYPE_BOT = 1
    TELEGRAM_BOT = 2

class Bot:
    """
    This class represents base class for bot instances
    """
    def __init__(self, name: str, bot_type:BotType, db_manager, iomanager=None):
        self.name = name
        self.bot_type = bot_type
        self.db_manager = db_manager
        self.iomanager = iomanager
        self.chats_settings = []
        self.commands = {}
        self.translator = GoogleTranslator(source='english')
        self.load_chats()
        self.logger = self.create_logger()

    def create_logger(self) -> logging.Logger:
        """
        function that creates file logger for bot instanse
        """
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        log_name = '../skype_bot.log' if self.bot_type == BotType.SKYPE_BOT else '../tg_bot.log'
        handler = logging.FileHandler(log_name, 'w', 'utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)
        return logger

    def load_bot_commands(self, path_to_file: str):
        """
        function that loads bot's commands and their answers from file
        """
        with open(path_to_file) as f:
            data = f.read()
            js = json.loads(data)
            self.commands = js

    def translate_text(self, text: str, source_language: str, target_language: str) -> str:
        """
        function that translates message from one language to other
        @:param text: message text
        @:param source_language: language to translate from
        @:param target_language: language to translate to
        @:return: translated text
        """
        self.translator.source = source_language
        self.translator.target = target_language
        return self.translator.translate(text)

    def send_translated_message(self, chat_id: Union[str, int], text: str,
                                source_language: str, target_language: str, reply_markup=None):
        """
        function that sends translated message to chat
        @:param chat_id: chat id to send message to
        @:param text: message text
        @:param source_language: language to translate from
        @:param target_language: language to translate to
        @:param reply_markup: reply markup to attach to message (not supported in Skype)
        """
        self.send_message(chat_id, self.translate_text(text, source_language, target_language), reply_markup)

    def get_chat_language(self, chat_id: Union[str, int], full=False) -> str:
        """
        function to get chat language
        @:param chat_id: chat id to get language from
        @:param full: True if function should return full language name, False if shortened ('english ; 'en')
        @:return str: chat language
        """
        cur_chat_settings = [setting for setting in self.chats_settings if str(setting.chat_id) == str(chat_id)]
        assert cur_chat_settings
        if not full:
            return cur_chat_settings[0].language
        else:
            return 'ukrainian' if cur_chat_settings[0].language == 'uk' else 'english'

    def update_chat_language(self, chat_id: Union[str, int], new_language: str) -> bool:
        """
        function that updates bot's interface in chat
        :param chat_id: chat id to change interface in
        :param new_language: new interface language
        :return: True if bot's interface was changed, False otherwise
        """
        language = self.get_chat_language(chat_id)
        if language == new_language:
            self.send_translated_message(chat_id, text='Interface language already ' + self.get_chat_language(chat_id, full=True),
                                         source_language='en', target_language=language)
            return False
        else:
            chats_table = self.get_chats_table_name()
            update_query = "update " + chats_table + " set language = '{0}' where chat_link = '{1}'"\
                .format(new_language, chat_id)
            self.db_manager.execute_query(update_query)
            # update local storage
            for i in range(len(self.chats_settings)):
                if str(self.chats_settings[i].chat_id) == str(chat_id):
                    self.chats_settings[i].language = new_language
            update_info = 'Interface language was changed on ' + self.get_chat_language(chat_id, full=True)
            self.send_translated_message(chat_id, update_info, source_language='en',
                                         target_language=new_language)
            return True

    def get_chats_table_name(self) -> str:
        """
        function that returns table name of bot's chats in DB
        :return:
        """
        if self.bot_type == BotType.SKYPE_BOT:
            return 'bot_skype_chats'
        elif self.bot_type == BotType.TELEGRAM_BOT:
            return 'bot_tg_chats'
        else:
            self.logger.error(self.get_chat_language.__name__ + ' wrong bot type')
            raise RuntimeError(self.get_chat_language.__name__)

    def load_chats(self):
        """
        function that loads bot's chats from remote Database into local storage
        """
        assert (self.db_manager is not None)
        chats_table = self.get_chats_table_name()
        query = "select * from " + chats_table
        res = self.db_manager.execute_query(query, fetch=True)
        for chat in res:
            self.chats_settings.append(BotChat(chat[1], chat[2], chat[3])) if self.bot_type == BotType.SKYPE_BOT else \
                self.chats_settings.append(BotChat(chat[1], chat[2], ''))

    def add_new_chat(self, chat_id: Union[str, int], *args) -> bool:
        """
        function that adds new chat in DB if there is no such chat yet
        @:param chat_id: chat id
        @:param chat_name: chat name
        @:param args: additional table arguments
        @:return: True if new chat was added to DB, False otherwise
        """
        table = self.get_chats_table_name()
        query = "select * from {0} where chat_link = '{1}'".format(table, chat_id)
        if not self.db_manager.execute_query(query, fetch=True):
            if self.bot_type == BotType.SKYPE_BOT:
                assert (len(args) == 1)
                chat_name = args[0]
                insert_query = "insert into {0} (chat_link, chat_name, language) " \
                               "values('{1}', '{2}', '{3}')".format(table, chat_id, chat_name, 'en')
                self.chats_settings.append(BotChat(chat_id, 'en', chat_name))
            else:
                insert_query = "insert into {0} (chat_link, language) values('{1}', '{2}')"\
                    .format(table, chat_id, 'en')
                self.chats_settings.append(BotChat(chat_id, 'en', ''))
            self.db_manager.execute_query(insert_query)
            self.logger.info('New chat ' + str(chat_id))
            return True
        return False

    def send_message(self, chat_id: Union[str, int], text: str, reply_markup=None):
        """
        function that sends message
        @:param chat_id: chat id to send message to
        @:param text: text message
        @:param markup: reply markup to attach to message (not supported in Skype)
        """
        raise NotImplementedError

    def is_message_from_group(self, chat_id: Union[str, int]) -> bool:
        """
        function that checks if message was sent from group chat or from private chat
        @:param chat_id: chat id to check
        @:return: True if message was sent from group chat, False otherwise
        """
        raise NotImplementedError

    def answer_on_command(self, command: str, chat_id: Union[str, int]):
        """
        function that sends answer on user's command
        @:param command: command to react on
        @:param chat_id: chat id in which command was sent
        """
        raise NotImplementedError

    def react_on_message(self, msg: Union[SkypeTextMsg,Message]):
        """
        function that reacts on messages in chat
        @:param: msg: message object
        """
        raise NotImplementedError
