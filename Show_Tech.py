from netmiko import ConnectHandler
from getpass import getpass
from datetime import datetime
import os

username = input("Enter your username: ")
password = getpass('Password: ')
switch_ip = input("Switch IP: ")

if __name__ == "__main__":
    cisco_device = {
        'device_type': 'cisco_ios',
        'host': switch_ip,
        'username': username,
        'password': password,
    }
    net_connect = ConnectHandler(**cisco_device)
    hostname = net_connect.send_command("show run | include hostname").split()[1]
    current_time = datetime.now().strftime("%m_%d_%y__%H_%M")
    filename = f'{hostname}_{current_time}_show_tech.txt'
    output = net_connect.send_command("show tech", read_timeout = 300)
    file_path = r'C:\Users\User\file_path'
    os.makedirs(file_path, exist_ok = True)
    full_file_path = os.path.join(file_path, filename)
    with open(full_file_path, 'w') as file:
        file.write(output)
    net_connect.disconnect()
    print(f"Backup config saved as '{filename}'")
