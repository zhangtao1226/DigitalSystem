# -*-coding : utf-8 -*
# @Author   : zhangTao
# @File     : test1.py
# @Time     : 2026/4/17 16:11
# @Desc     : 

import paramiko

def upload_file(local_path:str, remote_path:str, ip, user, password):
    transport = paramiko.Transport((ip, 22))
    transport.connect(username=user, password=password)

    sftp = paramiko.SFTPClient.from_transport(transport)

    sftp.put(local_path, remote_path)

    sftp.close()
    transport.close()
    print("上传成功")

if __name__ == "__main__":
    local_path = r"D:\ZT_Projects\Projects\DigitalSystem\placeholder.jpg"
    remote_path = r"E:\ZTProject\test.jpg"
    ip = "192.168.100.77"
    user = "Administrator"
    password = "12345678"

    upload_file(local_path, remote_path, ip, user, password)
