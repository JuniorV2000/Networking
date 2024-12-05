from netmiko import ConnectHandler
import re

def normalize_mac(mac):
    cleaned_mac = re.sub(r'[^a-fA-F0-9]', '', mac).lower()
    if len(cleaned_mac) == 12:
        return f"{cleaned_mac[:4]}.{cleaned_mac[4:8]}.{cleaned_mac[8:]}"
    else:
        raise ValueError("Invalid MAC address.")
    
username = input("Enter your username: ")
password = getpass('Password: ')
target_mac = input("MAC address: ")

try:
    target_mac = normalize_mac(target_mac)
except ValueError as e:
    print(e)
    exit()

with open('Routers.txt') as f:
    routers = [line.strip() for line in f if line.strip()]

def connect_device(ip, device_type):
    try:
        return ConnectHandler(device_type=device_type, ip=ip, username=username, password=password)
    except Exception as e:
        print(f"Failed to connect to {ip}: {e}")
        return None

def find_mac_address(device, mac):
    try:
        output = device.send_command(f"show mac address-table address {mac}")
        if mac in output:
            return output.splitlines()
    except Exception as e:
        print(f"Error executing MAC address table command on {device.host}: {e}")
    return None

def find_physical_interface(device, port):
    try:
        output = device.send_command("show etherchannel summary")
        for line in output.splitlines():
            if port in line:
                return [intf.split('(')[0] for intf in line.split() if intf.endswith("(P)")]
        print(f"No member interfaces found for {port}.")
    except Exception as e:
        print(f"Error finding physical interface for port {port}: {e}")
    return None

def find_cdp_neighbor(device, port):
    try:
        output = device.send_command(f"show cdp neighbors {port} detail")
        if "Invalid input" in output or "Total cdp entries displayed : 0" in output:
            return None, None

        # Check if the neighbor matches any AP model
        for line in output.splitlines():
            if any(model in line.upper() for model in AP_MODELS):
                print(f"AP Detected")
                return "AP_DETECTED", None
        return parse_cdp_output(output)
    except Exception as e:
        print(f"Error finding CDP neighbor on port {port}: {e}")
    return None, None

def parse_cdp_output(output):
    neighbor_id, neighbor_ip = None, None
    for line in output.splitlines():
        if "Device ID:" in line:
            neighbor_id = line.split("Device ID:")[1].strip()
        if "IP address:" in line:
            neighbor_ip = line.split("IP address:")[1].strip()
            print(f"Found neighbor {neighbor_id} at IP {neighbor_ip}")
            return neighbor_id, neighbor_ip
    return None, None

# List of AP models to identify
AP_MODELS = ["CW9164I", "C9105AXW", "C9130AXI", "C9120AXI", "CW9166"]

def trace_mac_recursive(device_ip, target_mac, visited_devices):
    if device_ip in visited_devices:
        print(f"Already visited device {device_ip}, stopping to avoid loops.")
        return False

    visited_devices.add(device_ip)
    device = connect_device(device_ip, 'cisco_ios')
    if not device:
        return False

    mac_info = find_mac_address(device, target_mac)
    if mac_info:
        for line in mac_info:
            if target_mac in line:
                port = line.split()[-1]
                print(f"MAC {target_mac} is on port {port} on {device_ip}")

                # Check CDP neighbor for this port
                neighbor_id, neighbor_ip = find_cdp_neighbor(device, port)
                if neighbor_id == "AP_DETECTED":
                    # Stop trace and display port configuration
                    print(f"Found AP connected to port {port} on device {device_ip}.")
                    show_interface_config(device, port, device_ip)
                    device.disconnect()
                    return True
                elif neighbor_id and neighbor_ip:
                    print(f"Continuing trace to {neighbor_id} at {neighbor_ip}.")
                    device.disconnect()
                    return trace_mac_recursive(neighbor_ip, target_mac, visited_devices)
                else:
                    # No CDP neighbor, print the interface config
                    print(f"No CDP neighbor found on port {port} of {device_ip}.")
                    show_interface_config(device, port, device_ip)
                    device.disconnect()
                    return True
    else:
        print(f"MAC {target_mac} not found on {device_ip}.")
    device.disconnect()
    return False


def show_interface_config(device, port, device_ip):
    try:
        running_config = device.send_command(f"show running-config interface {port}")
        filtered_config = "\n".join(
            line for line in running_config.splitlines()
            if not (line.startswith("Current configuration") or line.startswith("!") or line == "end" or line.startswith("Building configuration"))
        )
        print(f"Port found on switch {device_ip}: {port}")
        print(f"{filtered_config}\n")
    except Exception as e:
        print(f"Error displaying interface config for {port} on {device_ip}: {e}")

for router_ip in routers:
    if trace_mac_recursive(router_ip, target_mac, set()):
        break
