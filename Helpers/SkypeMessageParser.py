from skpy import SkypeTextMsg, SkypeChat
from Helpers.IOManager import Data

class ParserOutputData(Data):
    """
    This class represents structure for parsed message data
    """
    def __init__(self):
        super().__init__()
        self.should_react = True
        self.error_msg = ''
        self.command_token = ''
        self.has_attachment = False

    def __eq__(self, other):
        if not isinstance(other, ParserOutputData) or not isinstance(other, Data):
            return NotImplemented
        return self.group_name == other.group_name and self.sender_id == other.sender_id


class SkypeMessageParser:
    """
    This class represents message parser for skype bot class instance
    """
    def __init__(self, bot_id, command_tokens):
        self.bot_id = bot_id
        self.command_tokens = command_tokens

    def get_command_token(self, message:str) -> str:
        """
        this function retrieves command token from message. Only 1 token can be retrieved in one message
        :param message: message to find token in
        :return: token value
        """
        mentioned_token = ''
        for token in self.command_tokens:
            if message.find(token) != -1:
                mentioned_token = token
                break
        return mentioned_token

    def parse_chat_message(self, message:SkypeTextMsg, chat:SkypeChat) -> ParserOutputData:
        """
        this function parses skype chat message and fills structure ParserOutputData with parsed data
        :param message: skype message object
        :param chat: skype chat object
        :return: filled structure with parsed values
        """
        result = ParserOutputData()
        result.msg = message.plain
        # bot is not mentioned at all
        if result.msg.find(str(self.bot_id)) == -1:
            """ All commands can be handled from any user """
            result.command_token = self.get_command_token(result.msg)
            if result.command_token == '':
                result.should_react = False
            return result
        # bot is not mentioned at the start of the message
        if not self.is_bot_mentioned_at_the_beginning(result.msg):
            result.error_msg = 'Bot is not mentioned at the beginning of the message. ' \
                                  'Format is: @Bot @User1 @User2 !file(optional) ... text ...'
            return result
        user_ids = []
        mentioned_users = []
        for user_id in chat.userIds:
            if not user_id == self.bot_id and not user_id == message.userId:
                user_ids.append(user_id)
        result.msg = self.extract_mentioned_user_ids(result.msg, user_ids, mentioned_users)
        result.msg = self.extract_bot_id_from_message(result.msg)
        result.mentioned_user_ids = mentioned_users
        if result.msg.find('!file') != -1:
            result.msg = result.msg.replace('!file', '')
            result.msg = result.msg.lstrip()
            result.has_attachment = True
        result.sender_name = message.raw['imdisplayname']
        result.group_name = message.raw['threadtopic']
        result.sender_id = message.userId
        result.group_id = message.chatId
        # no text or not mentioned users except bot
        if result.msg == '' or not result.mentioned_user_ids:
            result.should_react = False
        return result

    def is_bot_mentioned_at_the_beginning(self, message:str) -> bool:
        """
        this function checks if skype bot is mentioned at the beginning of the message
        :param message: text message
        :return: True if bot is mentioned at the beginning, False otherwise
        """
        # remove whitespaces from left
        message = message.lstrip()
        return message.find(self.bot_id) == 1

    def extract_bot_id_from_message(self, message:str) -> str:
        """
        this function removes bot id from message
        :param message: text message
        :return: text message with extracted bot id
        """
        start = message.find('@' + self.bot_id, 0)
        if start != -1:
            message = message[:start] + message[start + len(self.bot_id) + 1:]
        message = message.lstrip()
        return message

    def extract_mentioned_user_ids(self, message:str, user_ids, mentioned_users:list[str]) -> str:
        """
        this function removes mentioned users` ids from message
        :param message: text message
        :param user_ids: all users ids in chat
        :param mentioned_users: mentioned users
        :return: text message with extracted mentioned users
        """
        mentioned_users.clear()
        # special case @all == <at id="*">все</at>
        all_mention_start = message.find('<at id="*">', 0)
        all_mentioned_end = message.find('</at>', all_mention_start)
        full_group = False
        if all_mention_start != -1 and all_mentioned_end != -1:
            full_group = True
            message = message[:all_mention_start] + message[all_mentioned_end + len('</at>'):]
        for user_id in user_ids:
            if full_group:
                mentioned_users.append(user_id)
            else:
                mention = '@' + user_id
                start = message.find(mention, 0)
                if start != -1:
                    mentioned_users.append(user_id)
            message = message.replace('@' + user_id, '')
        message = message.lstrip()
        return message
