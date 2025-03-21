import os
import time
import argparse
import json
import subprocess
import itertools
from collections import defaultdict

def create_bridge(bridge_name):
    """Create an OVS bridge if it doesn't exist"""
    os.system(f"ovs-vsctl --may-exist add-br {bridge_name}")
    print(f"Created bridge: {bridge_name}")

def create_sf(pf_num, sf_num, sf_index, driver_counter):
    """Create a Scalable Function and return its interface name"""
    os.system(f"/opt/mellanox/iproute2/sbin/mlxdevm port add pci/0000:03:00.{pf_num} flavour pcisf pfnum {pf_num} sfnum {sf_num}")
    time.sleep(1)

    os.system(f"/opt/mellanox/iproute2/sbin/mlxdevm port function set pci/0000:03:00.{pf_num}/{sf_index} hw_addr 00:00:00:00:0{pf_num}:{sf_num} trust on state active")
    print(f"SF Index pci/0000:03:00.{pf_num}/{sf_index} created.")
    time.sleep(1)
    
    print(f"Binding driver for SF {sf_num}...")
    os.system(f"echo mlx5_core.sf.{driver_counter} > /sys/bus/auxiliary/drivers/mlx5_core.sf_cfg/unbind")
    time.sleep(0.5)
    os.system(f"echo mlx5_core.sf.{driver_counter} > /sys/bus/auxiliary/drivers/mlx5_core.sf/bind")
    print(f"Driver binded for SF Index pci/0000:03:00.{pf_num}/{sf_index}")
    
    interface_name = f"en3f{pf_num}pf{pf_num}sf{sf_num}"
    return interface_name, driver_counter

def add_port_to_bridge(bridge_name, port_name):
    """Add a port to an OVS bridge"""
    os.system(f"ovs-vsctl add-port {bridge_name} {port_name}")
    print(f"Added port {port_name} to bridge {bridge_name}")

def run_hairpin(driver1, driver2, hp_num):
    """Run the hairpin VNF between two SFs"""
    unique_prefix = f"hp{hp_num}_{int(time.time())}"
    cmd = f"./flow_hairpin_vnf_marcelo/build/doca_flow_hairpin_vnf -a auxiliary:mlx5_core.sf.{driver1},dv_flow_en=2 -a auxiliary:mlx5_core.sf.{driver2},dv_flow_en=2 --file-prefix={unique_prefix} &"
    print(f"Starting hairpin between drivers {driver1} and {driver2}: {cmd}")
    subprocess.run(cmd, shell=True, check=True)

def set_bidirectional_flow(bridge_name, port1, port2):
    """Set bidirectional flow rules between two ports"""
    os.system(f"ovs-ofctl add-flow {bridge_name} \"in_port={port1},actions=output:{port2}\"")
    os.system(f"ovs-ofctl add-flow {bridge_name} \"in_port={port2},actions=output:{port1}\"")
    print(f"Set bidirectional flow between {port1} and {port2} on {bridge_name}")

def add_physical_port(bridge_name, port_name):
    """Add physical port to a bridge"""
    os.system(f"ovs-vsctl add-port {bridge_name} {port_name}")
    os.system(f"ovs-vsctl add-port {bridge_name} pf{port_name[-1]}hpf")
    print(f"Added physical port {port_name} and pf{port_name[-1]}hpf to {bridge_name}")

def get_port_numbers(bridge_name):
    """Get port numbers for all ports in a bridge"""
    result = subprocess.run(f"ovs-ofctl show {bridge_name}", shell=True, capture_output=True, text=True)
    output = result.stdout
    port_numbers = {}
    
    for line in output.split('\n'):
        if 'port=' in line:
            parts = line.strip().split()
            port_num = parts[0].split('(')[0]
            port_name = parts[1].split(':')[0]
            port_numbers[port_name] = port_num
    
    return port_numbers

def main():
    parser = argparse.ArgumentParser(description="Create SF topology from JSON file")
    parser.add_argument("--topo", type=str, default="topology.json", help="Path to the topology JSON file")
    args = parser.parse_args()
    
    # Load the JSON topology
    with open(args.topo, 'r') as f:
        topology = json.load(f)
    
    switches = topology.get("switches", [])
    links = topology.get("links", [])
    
    # Initialize counters for SF creation
    sf_num_counter = 10
    driver_counter = 2
    pci_00_sf_index = 229408  # For PF 0
    pci_01_sf_index = 294944  # For PF 1
    
    # Create all bridges first
    for switch in switches:
        create_bridge(switch)
    
    # Track interfaces for each switch and ports that need hairpins
    switch_interfaces = defaultdict(list)
    hairpin_pairs = []
    sf_drivers = {}  # Track driver counters for each SF interface
    
    # Add physical ports first
    for link in links:
        if link.get("type") == "physical":
            switch = link.get("src")
            port = link.get("dst")
            if port.startswith("p"):
                add_physical_port(switch, port)
                switch_interfaces[switch].append(port)
                switch_interfaces[switch].append(f"pf{port[-1]}hpf")
    
    # Process SF links
    sf_links = [link for link in links if link.get("type") == "SF"]
    
    # Use PF0 for first half of links and PF1 for second half
    half_point = len(sf_links) // 2
    
    for i, link in enumerate(sf_links):
        src_switch = link.get("src")
        dst_switch = link.get("dst")
        
        # Determine which PF to use based on the link position
        pf_num = 0 if i < half_point else 1
        sf_index = pci_00_sf_index if pf_num == 0 else pci_01_sf_index
        
        # Create SF for source switch
        sf_src_name, src_driver = create_sf(pf_num, sf_num_counter, sf_index, driver_counter)
        sf_drivers[sf_src_name] = src_driver
        add_port_to_bridge(src_switch, sf_src_name)
        switch_interfaces[src_switch].append(sf_src_name)
        
        # Increment counters
        sf_num_counter += 1
        sf_index += 1
        driver_counter += 1
        if pf_num == 0:
            pci_00_sf_index += 1
        else:
            pci_01_sf_index += 1
        
        
        # Create SF for destination switch
        sf_dst_name, dst_driver = create_sf(pf_num, sf_num_counter, sf_index, driver_counter)
        sf_drivers[sf_dst_name] = dst_driver
        add_port_to_bridge(dst_switch, sf_dst_name)
        switch_interfaces[dst_switch].append(sf_dst_name)
        
        # Increment counters again
        sf_num_counter += 1
        driver_counter += 1
        if pf_num == 0:
            pci_00_sf_index += 1
        else:
            pci_01_sf_index += 1
        
        # Record the hairpin pair
        hairpin_pairs.append((sf_src_name, sf_dst_name))
    
    # Create hairpins between SF pairs
    for i, (sf1, sf2) in enumerate(hairpin_pairs):
        run_hairpin(driver1=sf_drivers[sf1], driver2=sf_drivers[sf2], hp_num=i)
        time.sleep(1)
    
    # Get port numbers for all switches
    switch_port_numbers = {}
    for switch in switches:
        switch_port_numbers[switch] = get_port_numbers(switch)
    
    # Set bidirectional flows within each switch
    for switch, interfaces in switch_interfaces.items():
        for port1, port2 in itertools.combinations(interfaces, 2):
            # If both ports exist on this switch
            if port1 in switch_port_numbers[switch] and port2 in switch_port_numbers[switch]:
                port1_num = switch_port_numbers[switch][port1]
                port2_num = switch_port_numbers[switch][port2]
                set_bidirectional_flow(switch, port1_num, port2_num)
    
    print("\nTopology setup complete!")

if __name__ == "__main__":
    main()