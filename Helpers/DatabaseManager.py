import psycopg2
import config as config
import threading

class Singleton(type):
    """
    This class represents singleton pattern metaclass
    """
    _instances = {}
    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class DatabaseManager(metaclass=Singleton):
    """
    This class creates connection with PostgreSQL Database
    """
    def __init__(self):
        print('DatabaseManager singleton created')
        self.connection = psycopg2.connect(database=config.db_name, user='postgres',
                                           password=config.db_user_password, host='127.0.0.1', port='5432')
        self.lock = threading.Lock()

    def execute_query(self, query:str, fetch=False):
        """
        this function executes DB query
        :param query: text of query
        :param fetch: True if query results should be fetched, False otherwise
        :return: query results or None
        """
        with self.lock:
            print('execute_query', query)
            cursor = self.connection.cursor()
            with cursor:
                cursor.execute(query)
                self.connection.commit()
                if fetch:
                    return cursor.fetchall()
            return None

    def __del__(self):
        self.connection.close()
        print('DatabaseConnector singleton removed')
