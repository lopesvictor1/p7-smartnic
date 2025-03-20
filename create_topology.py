import os
import time
import argparse
import subprocess
import re
import itertools


def setting_physical_ports(num_switches):
    # Add physical ports and HPF ports to first and last bridge
    print("\n\nAdding physical and HPF ports to first and last bridges...\n\n")
    os.system("ovs-vsctl add-port ovsbr0 p0")
    os.system("ovs-vsctl add-port ovsbr0 pf0hpf")

    os.system(f"ovs-vsctl add-port ovsbr{num_switches} p1")
    os.system(f"ovs-vsctl add-port ovsbr{num_switches} pf1hpf")
   
def create_sf(pf_num, sf_num, sf_index, driver_counter, switch):
    os.system(f"/opt/mellanox/iproute2/sbin/mlxdevm port add pci/0000:03:00.{pf_num} flavour pcisf pfnum {pf_num} sfnum {sf_num}")
    
    time.sleep(2)

    os.system(f"/opt/mellanox/iproute2/sbin/mlxdevm port function set pci/0000:03:00.{pf_num}/{sf_index} hw_addr 00:00:00:00:0{pf_num}:{sf_num} trust on state active")
    print(f"SF Index pci/0000:03:00.{pf_num}/{sf_index} created.")
    time.sleep(2)
    
    print("Binding drivers...")
    
    os.system(f"echo mlx5_core.sf.{driver_counter} > /sys/bus/auxiliary/drivers/mlx5_core.sf_cfg/unbind")
    time.sleep(0.5)
    os.system(f"echo mlx5_core.sf.{driver_counter} > /sys/bus/auxiliary/drivers/mlx5_core.sf/bind")
    print(f"Driver binded for SF Index pci/0000:03:00.{pf_num}/{sf_index}")
    
    time.sleep(0.5)
    os.system(f"ovs-vsctl add-port ovsbr{switch} en3f{pf_num}pf{pf_num}sf{sf_num}")
    print(f"\n\n Created SF Index pci/0000:03:00.{pf_num}/{sf_index}, bounded to driver mlx5_core.sf.{driver_counter} and connected to bridge ovsbr{switch}\n\n")
 

def run_hairpin(driver1, driver2, hp_num):
    unique_prefix = f"hp{hp_num}_{int(time.time())}"
    cmd = f"./flow_hairpin_vnf_marcelo/build/doca_flow_hairpin_vnf -a auxiliary:mlx5_core.sf.{driver1},dv_flow_en=2 -a auxiliary:mlx5_core.sf.{driver2},dv_flow_en=2 --file-prefix={unique_prefix} &"
    print(cmd)
    subprocess.run(cmd, shell=True, check=True)
    
    
def get_ovs_interfaces():
    # Run the ovs-vsctl show command and capture output
    result = subprocess.run("ovs-vsctl show", shell=True, capture_output=True, text=True)
    output = result.stdout

    bridges = {}
    current_bridge = None

    # Process each line
    for line in output.split("\n"):
        line = line.strip()

        # Detect bridge names
        if line.startswith("Bridge "):
            current_bridge = line.split(" ")[1]
            bridges[current_bridge] = []

        # Detect ports that match "p0", "p1", or start with "en"
        elif line.startswith("Port "):
            port_name = line.split(" ")[1]
            if re.match(r"^(p0|p1|en[\w\d]+)$", port_name):
                bridges[current_bridge].append(port_name)

    # Generate pairs of interfaces for each bridge
    bridge_pairs = {}
    for bridge, ports in bridges.items():
        bridge_pairs[bridge] = list(itertools.combinations(ports, 2))  # Generate pairs of interfaces

    return bridge_pairs

    
def set_bidirectional_flow(switch, port1, port2):
    os.system(f"ovs-ofctl add-flow {switch} \"in_port={port1},actions=output:{port2}\"")
    os.system(f"ovs-ofctl add-flow {switch} \"in_port={port2},actions=output:{port1}\"")
 
def main():
    parser = argparse.ArgumentParser(description="Create SF switch topology")
    parser.add_argument("--sw", type=int, required=True, help="Number of switches in the topology")
    parser.add_argument("--dir", type=int, required=False, default=0, help="If 0 bidirectional, If 1 direction p0->p1, If 2 direction p1->p0")
    args = parser.parse_args()
    
    num_switches = args.sw
    directional = args.dir    
    
    if num_switches < 2:
        print("Number of switches must be at least 2")
        return
    
    # Initialize SF counters
    pci_00_sf_index = 229408 
    pci_01_sf_index = 294944
    sf_num_counter = 10
    driver_counter = 2
    hp_num = 0
    
    # Create bridges if they don't exist
    for i in range(0, num_switches):
        os.system(f"ovs-vsctl --may-exist add-br ovsbr{i}")
        print(f"ovs-vsctl --may-exist add-br ovsbr{i}")
    
    setting_physical_ports(num_switches-1)
    
    for i in range(1, num_switches):
        if i < num_switches/2:
            create_sf(0, sf_num_counter, pci_00_sf_index, driver_counter, i-1)
            
            sf_num_counter += 1
            pci_00_sf_index += 1
            driver_counter += 1
            create_sf(0, sf_num_counter, pci_00_sf_index, driver_counter, i)
            sf_num_counter += 1
            pci_00_sf_index += 1
            driver_counter += 1
            
            run_hairpin(driver1=driver_counter-2, driver2=driver_counter-1, hp_num=hp_num)
            hp_num += 1
            
        else:
            create_sf(1, sf_num_counter, pci_01_sf_index, driver_counter, i-1)
            sf_num_counter += 1
            pci_01_sf_index += 1
            driver_counter += 1
            create_sf(1, sf_num_counter, pci_01_sf_index, driver_counter, i)
            sf_num_counter += 1
            pci_01_sf_index += 1
            driver_counter += 1
            
            run_hairpin(driver1=driver_counter-2, driver2=driver_counter-1, hp_num=hp_num)
            hp_num += 1
            
    # Run function and print result
    bridge_interface_pairs = get_ovs_interfaces()
    for bridge, pairs in bridge_interface_pairs.items():
        for pair in pairs:
            set_bidirectional_flow(bridge, pair[0], pair[1])
    
    
    exit(0)
        
    
        
    

            


if __name__ == "__main__":
    main()
    
    '''
import os
import time
import argparse

def create_sf(pci_dev, pf_num, sf_num, sf_index):
    """Create a Scalable Function and return its port name"""
    # Create SF
    os.system(f"/opt/mellanox/iproute2/sbin/mlxdevm port add pci/{pci_dev} flavour pcisf pfnum {pf_num} sfnum {sf_num}")
    
    # Calculate port function ID (this might need adjustment based on your system)
    if pci_dev == "0000:03:00.1":
        port_func_id = 294945 + (sf_num - 17)  # Assuming base of 294945 for SF 17
    else:  # 0000:03:00.0
        port_func_id = 229409 + (sf_num - 20)  # Assuming base of 229409 for SF 20
    
    # Set MAC address and activate
    mac_addr = f"00:00:00:00:{pf_num:02d}:{sf_num:02d}"
    os.system(f"/opt/mellanox/iproute2/sbin/mlxdevm port function set pci/{pci_dev}/{port_func_id} hw_addr {mac_addr} trust on state active")
    
    # Unbind and bind driver
    os.system(f"echo mlx5_core.sf.{sf_index} > /sys/bus/auxiliary/drivers/mlx5_core.sf_cfg/unbind")
    os.system(f"echo mlx5_core.sf.{sf_index} > /sys/bus/auxiliary/drivers/mlx5_core.sf/bind")
    
    # Determine port name
    if pci_dev == "0000:03:00.1":
        port_name = f"en3f1pf{pf_num}sf{sf_num}"
    else:  # 0000:03:00.0
        port_name = f"en3f0pf{pf_num}sf{sf_num}"
    
    return port_name

def add_port_to_bridge(bridge_name, port_name):
    """Add SF port to OVS bridge"""
    os.system(f"ovs-vsctl add-port {bridge_name} {port_name}")

def set_bidirectional_flow(bridge_name, port1, port2):
    """Set bidirectional flow rules between two ports"""
    os.system(f"ovs-ofctl add-flow {bridge_name} \"in_port={port1},actions=output:{port2}\"")
    os.system(f"ovs-ofctl add-flow {bridge_name} \"in_port={port2},actions=output:{port1}\"")

def main():
    parser = argparse.ArgumentParser(description="Create SF switch topology")
    parser.add_argument("--sw", type=int, required=True, help="Number of switches in the topology")
    args = parser.parse_args()
    
    num_switches = args.sw
    
    # Validate input
    if num_switches < 1:
        print("Number of switches must be at least 1")
        return
    
    # Initialize SF counters
    sf_num_counter = 17  # Start from SF 17 as in original script
    sf_index_counter = 4  # Start from SF index 4 as in original script
    
    # Create bridges if they don't exist
    for i in range(1, num_switches + 1):
        os.system(f"ovs-vsctl --may-exist add-br ovsbr{i}")
    
    # Add physical ports and HPF ports to first and last bridge
    print("\n\nAdding physical and HPF ports to first and last bridges...\n\n")
    os.system("ovs-vsctl add-port ovsbr1 p0")
    os.system("ovs-vsctl add-port ovsbr1 pf0hpf")
    
    last_bridge = f"ovsbr{num_switches}"
    os.system(f"ovs-vsctl add-port {last_bridge} p1")
    os.system(f"ovs-vsctl add-port {last_bridge} pf1hpf")
    
    time.sleep(1)
    
    # Create connections between switches
    bridge_connections = []
    
    # For each switch, create connections to the next switch
    for i in range(1, num_switches):
        print(f"\n\nConnecting switch {i} to switch {i+1}...\n\n")
        
        # Create SF for first switch
        if i <= 3:  # Use PCI device 0000:03:00.1 for first 3 switches
            pci_dev = "0000:03:00.1"
            pf_num = 1
        else:  # Use PCI device 0000:03:00.0 for remaining switches
            pci_dev = "0000:03:00.0"
            pf_num = 0
            
        sf_port1 = create_sf(pci_dev, pf_num, sf_num_counter, sf_index_counter)
        sf_num_counter += 1
        sf_index_counter += 1
        add_port_to_bridge(f"ovsbr{i}", sf_port1)
        time.sleep(0.5)
        
        # Create SF for second switch
        if i+1 <= 3:  # Use PCI device 0000:03:00.1 for first 3 switches
            pci_dev = "0000:03:00.1"
            pf_num = 1
        else:  # Use PCI device 0000:03:00.0 for remaining switches
            pci_dev = "0000:03:00.0"
            pf_num = 0
            
        sf_port2 = create_sf(pci_dev, pf_num, sf_num_counter, sf_index_counter)
        sf_num_counter += 1
        sf_index_counter += 1
        add_port_to_bridge(f"ovsbr{i+1}", sf_port2)
        time.sleep(0.5)
        
        # Store connection for flow rules
        bridge_connections.append((i, sf_port1, i+1, sf_port2))
    
    # Set bidirectional flow rules
    print("\n\nSetting bidirectional flow rules...\n\n")
    
    # Set flow rules for first bridge with physical port and HPF port
    if len(bridge_connections) > 0:
        # Connect p0 and pf0hpf to the SF port of the first bridge
        set_bidirectional_flow("ovsbr1", "p0", bridge_connections[0][1])
        set_bidirectional_flow("ovsbr1", "pf0hpf", bridge_connections[0][1])
    else:
        # If only one switch, connect p0 directly to p1
        set_bidirectional_flow("ovsbr1", "p0", "p1")
        set_bidirectional_flow("ovsbr1", "p0", "pf1hpf")
        set_bidirectional_flow("ovsbr1", "pf0hpf", "p1")
        set_bidirectional_flow("ovsbr1", "pf0hpf", "pf1hpf")
    
    # Set flow rules for last bridge with physical port and HPF port
    if len(bridge_connections) > 0:
        # Connect p1 and pf1hpf to the SF port of the last bridge
        last_sf_port = bridge_connections[-1][3]
        set_bidirectional_flow(last_bridge, "p1", last_sf_port)
        set_bidirectional_flow(last_bridge, "pf1hpf", last_sf_port)
    
    # Set flow rules for switch-to-switch connections
    for i in range(len(bridge_connections)-1):
        current_conn = bridge_connections[i]
        next_conn = bridge_connections[i+1]
        
        # Set flow from current switch's outgoing port to next switch's incoming port
        set_bidirectional_flow(f"ovsbr{current_conn[0]}", current_conn[1], next_conn[1])
        
        # Set flow from next switch's outgoing port to current switch's incoming port
        set_bidirectional_flow(f"ovsbr{next_conn[0]}", next_conn[1], current_conn[3])
        
        # Set flow in middle switches
        set_bidirectional_flow(f"ovsbr{current_conn[2]}", current_conn[3], next_conn[3])
    
    print("\n\nTopology setup complete!\n\n")

if __name__ == "__main__":
    main()
'''