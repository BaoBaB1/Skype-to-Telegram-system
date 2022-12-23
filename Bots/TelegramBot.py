#!/usr/bin/env python
# -*- coding: utf-8 -*-

import telebot
import config
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from Bots.Bot import *
from Helpers import MessageSendingManager
from Helpers.SubscriptionsManager import UserSubscriptionRequest, UserSubscription, SubscriptionsManager
from threading import Thread


class MarkupContext(Enum):
    """
    This class represents reply markup context
    """
    MAIN_MENU = 1
    SUB_MANAGEMENT_MENU = 2
    LANGUAGE_MENU = 3
    NONE = 4

class TelegramBot(Bot):
    """
    This class represents Telegram bot instance
    """
    def __init__(self):
        self.bot = telebot.TeleBot(config.tg_bot_token)
        Bot.__init__(self, self.bot.get_me().first_name, BotType.TELEGRAM_BOT, SubscriptionsManager())
        self.iomanager = MessageSendingManager.MessageSendingManager(self)
        self.load_bot_commands('../tg_bot_commands.txt')
        self.bot.set_my_commands([
            telebot.types.BotCommand(key, 'Enter to find out :)') for key in self.commands.keys() if key != 'default'
        ])
        self.commands['start'] = self.commands['start'].replace("{0}", str(self.name))
        self.logger.info('Telegram bot instance created')
        print('Telegram bot instance created')

        # it's required to place decorators and all Telegram bot handlers in constuctor because of wrapping bot object
        @self.bot.message_handler(commands=self.commands.keys())
        def command_reactor(message:Message):
            """
            this function reacts on commands sent by user
            :param message: message from user
            """
            if self.is_message_from_group(message.chat.id):  # do not react on messages from groups
                return
            self.add_new_chat(message.chat.id)
            message.text = message.text.replace('/', '')
            self.answer_on_command(message.text, message.chat.id)

        @self.bot.callback_query_handler(func=lambda call:True)
        def callback_reactor(call:CallbackQuery):
            """
            this function reacts on callbacks sent related on user's actions
            :param call: callback query
            """
            self.bot.answer_callback_query(call.id)
            chat_id = call.message.chat.id
            message_id = call.message.message_id
            lang = self.get_chat_language(chat_id)
            if call.data == 'new_sub_request':
                self.bot.delete_message(chat_id, message_id)  # delete it to avoid multiple messages with reply markups
                req = UserSubscriptionRequest()
                thread = Thread(target=self.ask_for_skype_chat_id, args=(chat_id, req))
                thread.start()
            elif call.data == 'back_main_menu':
                text = self.translate_text(self.commands['default'], 'en', lang)
                self.edit_message_text_and_markup(chat_id, message_id, text, MarkupContext.MAIN_MENU)
            elif call.data == 'set_language':
                text = self.translate_text('Choose language', 'en', lang)
                self.edit_message_text_and_markup(chat_id, message_id, text, MarkupContext.LANGUAGE_MENU)
            elif call.data == 'en_language' or call.data == 'uk_language': 
                new_lang = 'en' if 'en' in call.data else 'uk'
                # sends new message
                self.update_chat_language(chat_id, new_lang)
                # make message with menu first
                self.bot.delete_message(chat_id, message_id)
                self.send_translated_message(
                    chat_id, self.commands['default'], 'en', new_lang, self.get_reply_markup(chat_id, MarkupContext.MAIN_MENU)
                )
            elif call.data == 'sub_management':
                text = self.translate_text('Choose management option', 'en', lang)
                self.edit_message_text_and_markup(chat_id, message_id, text, MarkupContext.SUB_MANAGEMENT_MENU)
            elif call.data == 'active_sub':
                subs = self.db_manager.get_user_subscriptions(chat_id, from_black_list=False)
                markup = self.get_subs_reply_markup(chat_id, subs, False)
                text = self.translate_text('Your subscriptions', 'en', lang)
                self.edit_message_text_and_markup(chat_id, message_id, text, MarkupContext.NONE, markup)
            elif call.data == 'blacklist_sub':
                subs = self.db_manager.get_user_subscriptions(chat_id, from_black_list=True)
                markup = self.get_subs_reply_markup(chat_id, subs, True)
                text = self.translate_text('Your blacklist', 'en', lang)
                self.edit_message_text_and_markup(chat_id, message_id, text, MarkupContext.NONE, markup)
            elif 'to_blacklist_' in call.data:
                record_id = call.data[len('to_blacklist_'):]
                print("to blacklist = ", record_id)
                self.db_manager.change_subscription_state(record_id, True)
                updated_keyboard = self.update_markup_keyboard(call.message.reply_markup.keyboard, record_id)
                self.bot.edit_message_reply_markup(chat_id, message_id, reply_markup=InlineKeyboardMarkup(updated_keyboard))
            elif 'from_blacklist_' in call.data:
                record_id = call.data[len('from_blacklist_'):]
                print("from blacklist = ", record_id)
                self.db_manager.change_subscription_state(record_id, False)
                updated_keyboard = self.update_markup_keyboard(call.message.reply_markup.keyboard, record_id)
                self.bot.edit_message_reply_markup(chat_id, message_id, reply_markup=InlineKeyboardMarkup(updated_keyboard))
            elif 'delete_' in call.data:
                record_id = call.data[len('delete_'):]
                print('delete sub ', record_id)
                self.db_manager.delete_subscription(record_id)
                updated_keyboard = self.update_markup_keyboard(call.message.reply_markup.keyboard, record_id)
                self.bot.edit_message_reply_markup(chat_id, message_id, reply_markup=InlineKeyboardMarkup(updated_keyboard))

    def update_markup_keyboard(self, keyboard:list[list[InlineKeyboardButton]], id_token:str) -> list[list[InlineKeyboardButton]]:
        """
        this function removes buttons row from keyboard
        :param keyboard: keyboard to remove row buttons from
        :param id_token: token of button to define which row should be deleted
        :return: updated keyboard
        """
        for item in keyboard:
            for button in item:
                if id_token in button.callback_data:
                    keyboard.remove(item)
                    break
        return keyboard

    def get_subs_reply_markup(self, chat_id, subs:list[UserSubscription], blacklist:bool) -> InlineKeyboardMarkup:
        """
        this function creates reply markup based on user subscriptions
        :param chat_id: chat id with user
        :param subs: list of user subscriptions
        :param blacklist: True if markup should contain blacklist subscriptions, False otherwise
        :return: created inline keyboard markup
        """
        lang = self.get_chat_language(chat_id)
        to_black = self.translate_text('To blacklist', 'en', lang)
        delete = self.translate_text('Delete', 'en', lang)
        make_active = self.translate_text('Make active', 'en', lang)
        back = self.translate_text('Back', 'en', lang)
        keyboard = []
        if not subs:
            keyboard.append([InlineKeyboardButton
                             ('Nothing in blacklist' if blacklist else 'You don\'t have any subscription yet',
                              callback_data='nothing')])
            self.translate_keyboard_buttons(chat_id, keyboard)
        else:
            for sub in subs:
                if not blacklist:
                    keyboard.append([
                        InlineKeyboardButton(sub.chat_name, callback_data='nothing'),
                        InlineKeyboardButton(to_black, callback_data='to_blacklist_' + str(sub.record_id)),
                        InlineKeyboardButton(delete, callback_data='delete_' + str(sub.record_id))
                        ])
                else:
                    keyboard.append([
                        InlineKeyboardButton(sub.chat_name, callback_data='nothing'),
                        InlineKeyboardButton(make_active, callback_data='from_blacklist_' + str(sub.record_id)),
                        InlineKeyboardButton(delete, callback_data='delete_' + str(sub.record_id))
                        ])
        self.add_back_button(keyboard, button_text=back, callback_text='sub_management')
        return InlineKeyboardMarkup(keyboard)

    def edit_message_text_and_markup(self, chat_id, message_id, new_text, markup_context:MarkupContext, markup=None):
        """
        this function edits messages text and reply markup of already sent bot's messages
        :param chat_id: chat id with user
        :param message_id: bot's message id
        :param new_text: new text of message
        :param markup_context: markup context
        :param markup: created earlier markup object. None by default
        """
        self.bot.edit_message_text(new_text, chat_id, message_id)
        if markup is None:
            markup = self.get_reply_markup(chat_id, markup_context)
        self.bot.edit_message_reply_markup(chat_id, message_id, reply_markup=markup)

    def ask_for_skype_chat_id(self, chat_id, req:UserSubscriptionRequest):
        """
        this function asks user to send skype chat id where user want to interact with bot
        :param chat_id: chat id with user
        :param req: structure for saving user's sent information
        """
        text = self.translate_text(
            'Send me skype chat id where you want me to interact with you', 'en', self.get_chat_language(chat_id)
        )
        msg = self.bot.send_message(chat_id, text)
        self.bot.register_next_step_handler(msg, self.get_skype_chat_id, req)

    def get_skype_chat_id(self, message:Message, req:UserSubscriptionRequest):
        """
        this function gets user's sent skype chat id where user want to interact with bot
        and asks for user's skype id if user is not registered in system yet, otherwise creates new subscription
        :param message: user's message
        :param req: structure for saving user's sent information
        """
        req.skype_group_id = message.text
        chat_id = message.chat.id 
        chat_lang = self.get_chat_language(chat_id)
        is_already_present = "select c.user_id, chat_link from user_and_skype_chats c " \
                             "inner join system_user s on c.user_id = s.user_id and s.tg_id = '{0}' where chat_link = '{1}'"\
                             .format(message.from_user.id, message.text)
        # check if this user already created subscription on entered chat id
        if self.db_manager.execute_query(is_already_present, fetch=True):
            self.send_translated_message(
                chat_id, 'You have already created subscription on ' + message.text + ' skype chat ', 'en', chat_lang
            )
            self.send_translated_message(
                chat_id, self.commands['default'], 'en', chat_lang, self.get_reply_markup(chat_id, MarkupContext.MAIN_MENU)
            )
            return
        check_query = "select * from bot_skype_chats where chat_link = '{0}'".format(req.skype_group_id)
        skype_chat_res = self.db_manager.execute_query(check_query, fetch=True)
        # skype bot doesn't present in user's sent skype chat id
        if not skype_chat_res:
            self.send_translated_message(
                chat_id, 'Bot is not present in skype chat with id ' + req.skype_group_id, 'en', chat_lang
            )
            self.send_translated_message(
                chat_id, self.commands['default'], 'en', chat_lang, self.get_reply_markup(chat_id, MarkupContext.MAIN_MENU)
            )
            return
        assert (len(skype_chat_res) != 0)
        req.skype_group_name = skype_chat_res[0][3]
        skype_id_query = "select * from system_user where tg_id = '{0}'".format(message.from_user.id)
        res = self.db_manager.execute_query(skype_id_query, fetch=True)
        if not res:
            text = self.translate_text('Send me your skype id', 'en', chat_lang)
            msg = self.bot.send_message(chat_id, text)
            self.bot.register_next_step_handler(msg, self.get_user_skype_id, req)
        else:
            req.user_id = res[0][0]
            req.user_skype_id = res[0][1]
            self.create_subscription(chat_id, req)

    def get_user_skype_id(self, message: Message, req: UserSubscriptionRequest):
        """
        this function gets user's sent skype id and creates new subscription
        :param message: user's message
        :param req: structure for saving user's sent information
        """
        query = "select user_id from system_user where skype_id = '{0}'".format(message.text)
        lang = self.get_chat_language(message.chat.id)
        res = self.db_manager.execute_query(query, fetch=True)
        # check if user with such skype id already exists
        if res:
            self.send_translated_message(
                message.chat.id, 'User with id ' + message.text + ' already exists', 'en', lang
            )
            self.send_translated_message(
                message.chat.id, self.commands['default'], 'en', lang, self.get_reply_markup(message.chat.id, MarkupContext.MAIN_MENU)
            )
            return
        # new user
        query = "insert into system_user(skype_id, tg_id) values('{0}', '{1}') returning user_id;"\
                .format(message.text, message.from_user.id)
        req.user_id = self.db_manager.execute_query(query,fetch=True)[0][0]
        req.user_skype_id = message.text
        self.create_subscription(message.chat.id, req)

    def create_subscription(self, chat_id, req:UserSubscriptionRequest):
        """
        this function creates new subscription in DB
        :param chat_id: chat id with user
        :param req: structure with saved user's sent information
        """
        self.db_manager.add_new_subscription(req)
        chat_lang = self.get_chat_language(chat_id)
        self.send_translated_message(chat_id, 'New subscription has been successfully created', 'en', chat_lang)
        markup = self.get_reply_markup(chat_id, MarkupContext.MAIN_MENU)
        self.send_translated_message(chat_id, self.commands['default'], 'en', chat_lang, markup)

    def get_reply_markup(self, chat_id, cxt:MarkupContext) -> InlineKeyboardMarkup:
        """
        this function creates reply markup for message according to given content
        :param chat_id: chat id with user
        :param cxt: context for creating markup
        :return: inline keyboard markup
        """
        keyboard = None
        if cxt == MarkupContext.MAIN_MENU:
            keyboard = [
                [InlineKeyboardButton('Create new subscription', callback_data='new_sub_request')],
                [InlineKeyboardButton('Subscriptions management', callback_data='sub_management')],
                [InlineKeyboardButton('Set language', callback_data='set_language')],
            ]
        elif cxt == MarkupContext.LANGUAGE_MENU:
            keyboard = [
                [InlineKeyboardButton('English', callback_data='en_language')],
                [InlineKeyboardButton('Українська', callback_data='uk_language')],
            ]
            self.add_back_button(keyboard, 'Back to main menu', 'back_main_menu')
        elif cxt == MarkupContext.SUB_MANAGEMENT_MENU:
            keyboard = [
                [InlineKeyboardButton('Active subscriptions', callback_data='active_sub')],
                [InlineKeyboardButton('Blacklist subscriptions', callback_data='blacklist_sub')],
            ]
            self.add_back_button(keyboard, 'Back to main menu', 'back_main_menu')
        self.translate_keyboard_buttons(chat_id, keyboard)
        return InlineKeyboardMarkup(keyboard)

    def add_back_button(self, keyboard:list[list[InlineKeyboardButton]], button_text:str, callback_text:str):
        """
        this function add "back" button to existing keyboard
        :param keyboard: keyboard to add back button to
        :param button_text: back button text
        :param callback_text: back button callback text
        """
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_text)])

    def translate_keyboard_buttons(self, chat_id, keyboard:list[list[InlineKeyboardButton]]):
        """
        this function translates keyboard buttons in reply keyboard markup
        :param chat_id: chat id with user
        :param keyboard: keyboard with buttons
        """
        lang = self.get_chat_language(chat_id)
        if lang != 'en':
            for lst_item in keyboard:
                for button in lst_item:
                    # do not translate language buttons
                    if not button.callback_data == 'en_language' and not button.callback_data == 'uk_language':
                        button.text = self.translate_text(button.text, 'en', lang)

    def start_polling(self):
        """
        this function starts bot
        """
        self.bot.infinity_polling()

    # below functions defines base class Bot methods
    def react_on_message(self, msg: Union[SkypeTextMsg, Message]):
        """ this function just overrdies base method and does nothing """
        pass

    def send_message(self, chat_id: Union[str, int], text: str, reply_markup=None):
        self.bot.send_message(chat_id, text, reply_markup=reply_markup)

    def answer_on_command(self, command: str, chat_id: Union[str, int]):
        text = self.commands[command]
        reply_markup = None
        if command == 'start':
            reply_markup = self.get_reply_markup(chat_id, MarkupContext.MAIN_MENU)
        self.send_translated_message(chat_id, text, 'en', self.get_chat_language(chat_id), reply_markup)

    def is_message_from_group(self, chat_id: Union[str, int]) -> bool:
        return self.bot.get_chat_members_count(chat_id) > 2


if __name__ == '__main__':
    wrapped_bot = TelegramBot()
    wrapped_bot.start_polling()
