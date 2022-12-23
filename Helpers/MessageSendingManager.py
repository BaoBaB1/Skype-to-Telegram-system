from Bots import TelegramBot
from Helpers.IOManager import IOManager, Data
from threading import Thread
import time
import re
import pathlib
import os
import config as config
import requests

class MessageSendingManager(IOManager, Thread):
    """
    This class represents manager for sending messages to users` Telegram chats with bot
    """
    def __init__(self, bot:TelegramBot.TelegramBot):
        IOManager.__init__(self)
        Thread.__init__(self)
        self.bot_ref = bot
        self.start()

    def run(self):
        while True:
            for filename in os.listdir(self.path):
                file = os.path.join(self.path, filename)
                # parse only txt files
                # pattern is %m_%d_%Y_%H_%M_%S
                if os.path.isfile(file) and pathlib.Path(file).suffix == '.txt' \
                        and re.search(r'\d{2}_\d{2}_\d{4}_\d{2}_\d{2}_\d{2}', filename) is not None:
                    print(file)
                    data = self.read_message_from_file(filename)
                    # get user ids who subscribed on message resending from group data.group_id
                    # and who don't have this group in blacklist
                    query = "select c.user_id from user_and_skype_chats c " \
                            "inner join system_user s on s.user_id = c.user_id " \
                            "where c.chat_link = '" + str(data.group_id) + "' and c.is_in_blacklist = 'n'"
                    res = self.bot_ref.db_manager.execute_query(query, fetch=True)
                    print(res)
                    if res:
                        try:
                            res = self.get_mentioned_users_tg_ids(res, data)
                            self.send_message_to_mentioned_users(res, data)
                        except Exception as e:
                            self.bot_ref.logger.error(str(e))

            time.sleep(5)

    def get_mentioned_users_tg_ids(self, query_res, data:Data):
        """
        this function gets users Telegram ids from query result
        :param query_res: select query result
        :param data: data structure with read information from file
        :return: query result with mentioned user ids
        """
        mentioned_users_ids = ''
        for r in query_res:
            mentioned_users_ids += str(r[0]) + ', '
        mentioned_users_ids = mentioned_users_ids.removesuffix(', ')
        mentioned_users_str = ''
        for user_id in data.mentioned_user_ids:
            mentioned_users_str += user_id + ', '
        mentioned_users_str = mentioned_users_str.removesuffix(', ')
        query = "select tg_id from system_user where user_id in ({0}) and skype_id in ('{1}')" \
            .format(mentioned_users_ids, mentioned_users_str)
        return self.bot_ref.db_manager.execute_query(query, fetch=True)

    def send_message_to_mentioned_users(self, query_res, data:Data):
        """
        this function sends read message from file to mentioned users in it to their private chats in Telegram
        :param query_res: select query result
        :param data: data structure with read information from file
        """
        for tg_id in query_res:
            print('sending ...')
            text = self.bot_ref.translate_text(data.to_str(), 'en', self.bot_ref.get_chat_language(tg_id[0]))
            self.bot_ref.send_message(tg_id[0], text + '\n' + data.msg)
            # self.bot_ref.send_message(tg_id[0], str(data) + ('\nIn addition this file was attached:' if data.attachment_name != '' else ''))
            if data.attachment_name != '':
                file_location = self.path + data.attachment_name
                with open(file_location, "rb") as at:
                    send_doc = 'https://api.telegram.org/bot' + config.tg_bot_token + '/sendDocument?'
                    req_data = {
                        'chat_id': str(tg_id[0])
                    }
                    files = {
                        'document': at
                    }
                    requests.post(send_doc, data=req_data, files=files)
                os.remove(self.path + data.attachment_name)
