import threading
from Helpers.DatabaseManager import DatabaseManager

class UserSubscriptionRequest:
    """
    This class represents structure for saving user inputs
    """
    def __init__(self):
        self.user_id = ''
        self.user_skype_id = ''
        self.skype_group_name = ''
        self.skype_group_id = ''

class UserSubscription:
    """
    This class represents structure for saving user subscriptions info
    """
    def __init__(self, record_id, chat_link, chat_name):
        self.record_id = record_id
        self.chat_link = chat_link
        self.chat_name = chat_name


class SubscriptionsManager(DatabaseManager):
    """
    This class represents manager for CRUD operations with subscriptions
    """
    def __init__(self):
        super().__init__()
        self.insert_lock = threading.Lock()
        self.update_lock = threading.Lock()
        self.delete_lock = threading.Lock()

    def add_new_subscription(self, req:UserSubscriptionRequest):
        """
        this function adds new subsctiption to DB
        :param req: filled structure to read data from
        """
        with self.insert_lock:
            # try to add user's sent skype chat id to chats table.
            # it may be already there because earlier somebody from this chat has already created subscription
            print(req.user_id, req.user_skype_id, req.skype_group_id, req.skype_group_name, sep=' ')
            query = "select * from skype_chat where chat_link = '{0}'".format(req.skype_group_id)
            res = self.execute_query(query, fetch=True)
            if not res:
                query = "insert into skype_chat(chat_link, chat_name) values('{0}','{1}')"\
                    .format(req.skype_group_id, req.skype_group_name)
                self.execute_query(query)
            query = "insert into user_and_skype_chats(user_id, chat_link, is_in_blacklist) values('{0}', '{1}', 'n')"\
                .format(req.user_id, req.skype_group_id)
            self.execute_query(query)

    def change_subscription_state(self, record_id, to_blacklist:bool):
        """
        this function updates subscription state in DB (from active to inactive and vice versa)
        :param record_id: subscription record id in DB
        :param to_blacklist: True if subscription should be added to blacklist, False otherwise
        """
        with self.update_lock:
            query = "update user_and_skype_chats set is_in_blacklist = '{0}' where record_id = {1}"\
                .format('y' if to_blacklist else 'n', record_id)
            self.execute_query(query)

    def delete_subscription(self, record_id):
        """
        this function deletes user's subscription from DB
        :param record_id: subscription record id in DB
        """
        with self.delete_lock:
            query = "delete from user_and_skype_chats where record_id = {0}".format(record_id)
            self.execute_query(query)

    def get_user_subscriptions(self, chat_id, from_black_list) -> list[UserSubscription]:
        """
        this function gets all user's subscriptions
        :param chat_id: chat id with user
        :param from_black_list: True if all blacklist subscriptions should be retrived, False otherwise
        :return: list of user's subscriptions
        """
        # chat id == user_id in private messages
        query = "select user_id from system_user where tg_id = '{0}'".format(chat_id)
        res = self.execute_query(query, fetch=True)
        if not res:  # no subscriptions
            return []
        user_id_in_system = res[0][0]
        subs: list[UserSubscription] = []
        query = "select c.record_id, c.chat_link, s.chat_name from user_and_skype_chats c " \
                "inner join skype_chat s on s.chat_link = c.chat_link " \
                "where user_id = '{0}' and c.is_in_blacklist = '{1}'".format(user_id_in_system, 'y' if from_black_list else 'n')
        res = self.execute_query(query, fetch=True)
        for sub in res:
            print(sub)
            subs.append(UserSubscription(sub[0], sub[1], sub[2]))
        return subs
