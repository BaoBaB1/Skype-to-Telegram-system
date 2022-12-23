import threading
import datetime as dt
import codecs
import os

class Data:
    """
    This class represents structure for saving read/written data
    """
    def __init__(self):
        self.sender_id = ''
        self.sender_name = ''
        self.group_name = ''
        self.group_id = ''
        self.mentioned_user_ids = []
        self.msg = ''
        self.attachment_name = ''
        self.attachment = None

    def remove_whitespaces(self):
        """
        this function removes whitespaces from field values
        """
        self.sender_name = self.sender_name.strip()
        self.group_name = self.group_name.strip()
        self.group_id = self.group_id.strip()
        self.attachment_name = self.attachment_name.strip()
        self.msg = self.msg.strip()
        for i in range(len(self.mentioned_user_ids)):
            self.mentioned_user_ids[i] = self.mentioned_user_ids[i].strip()

    def to_str(self):
        return self.sender_name + ' sent you message from group ' + "'" + self.group_name + "'" + ':\n' + \
               ('In addition this file was attached:' if self.attachment_name != '' else '')

class IOManager:
    """
    This class represents input/output manager for data
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.lock2 = threading.Lock()
        self.path = 'D:/message_storage/'
        exists = os.path.exists(self.path)
        if not exists:
            os.makedirs(self.path)

    def read_message_from_file(self, file:str) -> Data:
        """
        this function reads message from file which should be sent to users
        :param file: file name
        :return: filled Data structure
        """
        with self.lock2:
            read_data = Data()
            with open(os.path.join(self.path + file), 'r', encoding='utf-8') as f:
                read_data.sender_name = f.readline()
                read_data.group_name = f.readline()
                read_data.group_id = f.readline()
                mentioned_cnt = int((f.readline()).strip())
                for i in range(mentioned_cnt):
                    read_data.mentioned_user_ids.append(f.readline())
                read_data.msg = f.readline()
                if f.readline().strip() == '1':
                    attachment_name = f.readline()
                    read_data.attachment_name = attachment_name
            os.remove(self.path + file)
            read_data.remove_whitespaces()
            return read_data

    def write_message_to_file(self, out:Data):
        """
        this function writes message data which should be sent to file
        :param out: data structure to write info from
        """
        with self.lock:
            ts = dt.datetime.now()
            time = ts.strftime("%m_%d_%Y_%H_%M_%S")
            f = codecs.open(self.path + time + ".txt", 'w', 'utf-8')
            f.write(out.sender_name + '\n')
            f.write(out.group_name + '\n')
            f.write(out.group_id + '\n')
            # live:.cid.b7c39b3e0953931c
            #f.write('1' + '\n')
            #f.write('live:.cid.b7c39b3e0953931c' + '\n')
            f.write(str(len(out.mentioned_user_ids)) + '\n')
            for user_id in out.mentioned_user_ids:
                f.write(str(user_id) + '\n')
            print('msg = ', out.msg)
            f.write(out.msg + '\n')
            if out.attachment_name != '':
                f.write('1' + '\n')
                attachment_file_name = str(time) + '_' + out.attachment_name
                f.write(attachment_file_name)
                with open(os.path.join(self.path + attachment_file_name), "wb") as f2:
                    f2.write(out.attachment)
            else:
                f.write('0')
            f.close()
