#!/usr/bin/env python3
"""
Created by Claude AI assistant (3.7 Sonnet)
Hierarchy-Preserving NPS XML Merger Script - Merges multiple Windows NPS export XML files
while preserving the correct hierarchical structure and deduplicating elements.

Generic Hierarchy-Preserving XML Merger Script

This script merges multiple XML files while preserving the hierarchical structure
and deduplicating elements that have <Properties> as a child element.
Particularly useful for Windows NPS export files and similar hierarchical configurations.

Usage:
    python xml_merger.py [options] input1.xml input2.xml [input3.xml ...] -o output.xml

Options:
    -o, --output      Output file path (default: merged.xml)
    -v, --verbose     Enable verbose output
    -h, --help        Show help message
"""

import os
import sys
import argparse
import xml.etree.ElementTree as ET
from collections import defaultdict

def parse_xml_file(file_path):
    """Parse an XML file with error handling."""
    try:
        return ET.parse(file_path)
    except ET.ParseError as e:
        print(f"Error parsing {file_path}: {str(e)}")
        print("Please ensure your XML file is properly formatted.")
        raise

def get_element_id(element):
    """Generate a unique identifier for an element based on tag and name attribute."""
    name = element.get('name', '')
    return f"{element.tag}:{name}"

def get_element_path(element, root):
    """
    Attempt to construct the hierarchical path to this element.
    Returns a list of (tag, name_attr) tuples representing the path.
    """
    path = []
    current = element
    
    # This is a very simplified approach since ElementTree doesn't track parents
    # In a real scenario, we'd need to search through the entire tree
    
    # Just return the element's tag since we can't easily determine the path
    path.append((element.tag, element.get('name', '')))
    return path

def find_parent_by_path(root, path):
    """
    Find a parent element in the XML tree based on a path of (tag, name) tuples.
    """
    if not path:
        return None
    
    # Start with all potential parent candidates
    candidates = [root]
    
    # For each step in the path, filter down to matching elements
    for tag, name in path[:-1]:  # Skip the last one as it's the element itself
        new_candidates = []
        for candidate in candidates:
            for child in candidate:
                if child.tag == tag and child.get('name', '') == name:
                    new_candidates.append(child)
        candidates = new_candidates
        if not candidates:
            return None
    
    # Return the first matching candidate, if any
    return candidates[0] if candidates else None

def find_matching_parent(base_root, element_tag, element_name, target_parent_tag=None):
    """
    Find the appropriate parent in the base XML for an element with the given tag and name.
    
    Args:
        base_root: The root element of the base XML tree
        element_tag: The tag of the element to place
        element_name: The name attribute of the element to place
        target_parent_tag: If provided, look for a parent with this specific tag
        
    Returns:
        The appropriate parent element, or None if no suitable parent is found
    """
    # If a specific parent tag is provided, look for it
    if target_parent_tag:
        parents = base_root.findall(f".//*[tag='{target_parent_tag}']")
        if parents:
            return parents[0]
    
    # Look for existing siblings with the same tag
    siblings = base_root.findall(f".//*/{element_tag}")
    if siblings:
        # Return the parent of the first sibling
        for parent in base_root.findall(".//*"):
            for child in parent:
                if child.tag == element_tag:
                    return parent
    
    # If no siblings found, try to find a "Children" container
    children_containers = base_root.findall(".//Children")
    if children_containers:
        # Look for an appropriate container by checking its immediate children
        for container in children_containers:
            # If this container already has similar elements, use it
            has_similar = False
            for child in container:
                if child.tag == element_tag or child.tag.endswith(element_tag.split('_')[-1]):
                    has_similar = True
                    break
            if has_similar:
                return container
        
        # If no suitable container found, use the first one
        # This is a fallback and might not be ideal
        return children_containers[0]
    
    # Last resort: return the root element
    return base_root

def get_existing_parent_map(root):
    """
    Create a map of each tag to its potential parent tags in the existing XML.
    This helps determine where new elements should go.
    """
    parent_map = defaultdict(set)
    
    # For each element in the tree, record its children's tags
    for parent in root.findall(".//*"):
        for child in parent:
            parent_map[child.tag].add(parent.tag)
    
    return parent_map

def find_correct_parent(base_root, element, source_root=None):
    """
    Find the correct parent in the base XML tree for the given element.
    
    This function handles specific rules for NPS XML files:
    1. RADIUS clients should go under Microsoft_Radius_Protocol/Children/Clients/Children
    2. RadiusProfiles should go under RadiusProfiles/Children
    3. Network Policies should go under NetworkPolicy/Children
    
    Args:
        base_root: The root element of the base XML
        element: The element to place
        source_root: The root element of the source XML (for context)
        
    Returns:
        The appropriate parent element in the base XML
    """
    element_tag = element.tag
    element_name = element.get('name', '')
    
    # Check if this element has a Properties child
    has_properties = any(child.tag == "Properties" for child in element)
    
    # Helper function to check if an element exists at a specific path
    def find_path(root, path):
        current = root
        for segment in path.split('/'):
            if not segment:
                continue
            found = False
            for child in current:
                if child.tag == segment:
                    current = child
                    found = True
                    break
            if not found:
                return None
        return current
    
    # Handle RADIUS clients - elements with IP_Address in Properties
    if has_properties:
        properties = element.find("./Properties")
        if properties is not None:
            has_ip = any(prop.tag == "IP_Address" for prop in properties)
            if has_ip:
                # This is a RADIUS client, look for the clients container
                client_path = "Children/Microsoft_Internet_Authentication_Service/Children/Protocols/Children/Microsoft_Radius_Protocol/Children/Clients/Children"
                clients_container = find_path(base_root, client_path)
                if clients_container is not None:
                    return clients_container
                
                # Fallback: try a simpler path search
                clients_containers = base_root.findall(".//Clients/Children")
                if clients_containers:
                    return clients_containers[0]
    
    # Look for the exact same parent path structure in the base XML
    if source_root is not None:
        # Try to determine the parent's path in the source XML
        for parent in source_root.findall(".//*"):
            for child in parent:
                if child == element or (child.tag == element.tag and child.get('name') == element_name):
                    # Found the parent in the source, now find the same path in base
                    parent_tag = parent.tag
                    parent_name = parent.get('name', '')
                    
                    # Look for a matching parent in the base XML
                    for base_parent in base_root.findall(f".//*[@name='{parent_name}']"):
                        if base_parent.tag == parent_tag:
                            return base_parent
                    
                    # If no exact match, try just the tag
                    for base_parent in base_root.findall(f".//{parent_tag}"):
                        return base_parent
    
    # Handle specific NPS elements by likely container
    known_containers = {
        # For RadiusProfiles
        "RadiusProfiles": "Children/Microsoft_Internet_Authentication_Service/Children/RadiusProfiles/Children",
        # For NetworkPolicy
        "NetworkPolicy": "Children/Microsoft_Internet_Authentication_Service/Children/NetworkPolicy/Children",
        # For Proxy_Policies
        "Proxy_Policies": "Children/Microsoft_Internet_Authentication_Service/Children/Proxy_Policies/Children",
        # For Proxy_Profiles
        "Proxy_Profiles": "Children/Microsoft_Internet_Authentication_Service/Children/Proxy_Profiles/Children",
        # For RADIUS server groups
        "RADIUS_Server_Groups": "Children/Microsoft_Internet_Authentication_Service/Children/RADIUS_Server_Groups/Children",
        # For Vendors
        "Vendors": "Children/Microsoft_Internet_Authentication_Service/Children/Protocols/Children/Microsoft_Radius_Protocol/Children/Vendors/Children"
    }
    
    # First check direct element tag match
    for container_name, path in known_containers.items():
        if element_tag == container_name:
            container = find_path(base_root, path)
            if container is not None:
                return container
    
    # Then check if the element belongs in one of these containers
    for container_name, path in known_containers.items():
        # Look for existing elements with same tag in this container
        container = find_path(base_root, path)
        if container is not None:
            for child in container:
                if child.tag == element_tag:
                    return container
    
    # Look for a Children element that already has this element's tag
    for children in base_root.findall(".//Children"):
        for child in children:
            if child.tag == element_tag:
                return children
    
    # Last resort - find a generic Children container
    children_containers = base_root.findall(".//Children")
    if children_containers:
        return children_containers[0]
    
    # Absolute last resort: return the root
    return base_root

def merge_xml_files(input_files, output_file, verbose=False):
    """
    Merge multiple XML files, preserving hierarchy and deduplicating elements with Properties.
    
    Args:
        input_files: List of input XML file paths
        output_file: Path to the output merged XML file
        verbose: Whether to output verbose logs
    
    Returns:
        True if successful, False otherwise
    """
    if not input_files:
        print("Error: No input files provided")
        return False
    
    try:
        # Parse the base file
        print(f"Using {input_files[0]} as base file")
        base_tree = parse_xml_file(input_files[0])
        base_root = base_tree.getroot()
        
        # Track elements by their unique identifiers to avoid duplicates
        seen_elements = {}
        
        # First, catalog all existing elements in the base file that have Properties
        for elem in base_root.findall(".//*"):
            has_properties = any(child.tag == "Properties" for child in elem)
            if has_properties:
                key = get_element_id(elem)
                seen_elements[key] = elem
        
        if verbose:
            print(f"Found {len(seen_elements)} unique elements with Properties in base file")
        
        # Process each additional file
        for file_idx, file_path in enumerate(input_files[1:], 1):
            print(f"Merging file {file_idx}: {file_path}")
            try:
                merge_tree = parse_xml_file(file_path)
                merge_root = merge_tree.getroot()
                
                # Count of new elements added
                new_elements_count = 0
                
                # First, identify all elements with Properties in the merge file
                elements_with_properties = []
                for elem in merge_root.findall(".//*"):
                    has_properties = any(child.tag == "Properties" for child in elem)
                    if has_properties:
                        elements_with_properties.append(elem)
                
                if verbose:
                    print(f"  Found {len(elements_with_properties)} elements with Properties in {file_path}")
                
                # For each element with Properties, find its correct location in the base file
                for element in elements_with_properties:
                    # Create a unique identifier for this element
                    key = get_element_id(element)
                    
                    # Skip if we've already seen this element
                    if key in seen_elements:
                        if verbose:
                            print(f"  Skipping duplicate: {key}")
                        continue
                    
                    # Find the correct parent in the base XML
                    parent_in_base = find_correct_parent(base_root, element, merge_root)
                    
                    if parent_in_base is not None:
                        # Clone the element
                        new_element = ET.Element(element.tag)
                        new_element.attrib = element.attrib.copy()
                        
                        # Copy all children including Properties
                        for child in element:
                            child_elem = ET.SubElement(new_element, child.tag)
                            child_elem.attrib = child.attrib.copy()
                            if child.text:
                                child_elem.text = child.text
                            
                            # Copy grandchildren (especially for Properties)
                            for grandchild in child:
                                gc_elem = ET.SubElement(child_elem, grandchild.tag)
                                gc_elem.attrib = grandchild.attrib.copy()
                                if grandchild.text:
                                    gc_elem.text = grandchild.text
                        
                        # Add to the base XML
                        parent_in_base.append(new_element)
                        seen_elements[key] = new_element
                        new_elements_count += 1
                    else:
                        print(f"  Warning: Could not find appropriate parent for {key}")
                
                print(f"  Added {new_elements_count} new elements from {file_path}")
            
            except Exception as e:
                print(f"Error processing {file_path}: {str(e)}")
                if verbose:
                    import traceback
                    traceback.print_exc()
                print(f"Skipping this file and continuing with others.")
                continue
        
        # Write the merged tree to the output file
        try:
            # Add XML declaration and format the output
            with open(output_file, 'wb') as f:
                f.write(b'<?xml version="1.0" encoding="utf-8"?>\n')
                try:
                    ET.indent(base_tree)  # Python 3.9+ feature
                except AttributeError:
                    print("Note: XML indentation not available (requires Python 3.9+)")
                    
                base_tree.write(f, encoding='utf-8', xml_declaration=False)
            
            print(f"Successfully merged XML files into {output_file}")
            return True
        
        except Exception as e:
            print(f"Error writing output file: {str(e)}")
            return False
    
    except Exception as e:
        print(f"Error during merge process: {str(e)}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False

def main():
    parser = argparse.ArgumentParser(
        description='Merge XML files while preserving hierarchy and deduplicating elements with Properties children'
    )
    parser.add_argument('input_files', nargs='+', help='Input XML files to merge')
    parser.add_argument('-o', '--output', default='merged.xml', help='Output file (default: merged.xml)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()
    
    # Validate input files
    valid_files = []
    for file_path in args.input_files:
        if not os.path.exists(file_path):
            print(f"Warning: File not found: {file_path}")
        else:
            valid_files.append(file_path)
    
    if not valid_files:
        print("Error: No valid XML files to merge")
        return 1
    
    # Perform the merge
    success = merge_xml_files(valid_files, args.output, args.verbose)
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
