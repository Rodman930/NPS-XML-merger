#!/usr/bin/env python3
"""
Created by Claude AI assistant (3.7 Sonnet)
Hierarchy-Preserving NPS XML Merger Script - Merges multiple Windows NPS export XML files
while preserving the correct hierarchical structure and deduplicating elements.
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
    """Generate a unique identifier for an element."""
    name = element.get('name', '')
    return f"{element.tag}:{name}"

def get_full_path(element, root):
    """Try to determine the full hierarchical path to an element."""
    path = []
    current = element
    
    # Walk up the tree to build the path
    while current is not None and current != root:
        path.append((current.tag, current.get('name', '')))
        parent = current.getparent() if hasattr(current, 'getparent') else None
        current = parent
    
    # Reverse to get from root to element
    path.reverse()
    return path

def find_correct_parent(base_root, element, source_root):
    """
    Find the correct parent in the base XML tree for the given element.
    This uses knowledge of the NPS XML structure.
    """
    # First, identify what type of element this is and its expected location
    element_tag = element.tag
    element_name = element.get('name', '')
    
    # Check if element has Properties as a direct child
    has_properties = False
    for child in element:
        if child.tag == "Properties":
            has_properties = True
            break
    
    # Determine if this is a RadiusProfiles element
    if element_tag.endswith("_Infrastructure") or element_tag.endswith("Controller") or "Wireless_Access" in element_tag:
        # These elements typically go under RadiusProfiles/Children
        parent_path = "./Children/Microsoft_Internet_Authentication_Service/Children/RadiusProfiles/Children"
        parents = base_root.findall(parent_path)
        if parents:
            return parents[0]
    
    # Check if this is a RADIUS client (element with IP_Address property)
    properties = element.find("./Properties")
    if properties is not None:
        for prop in properties:
            if prop.tag == "IP_Address":
                # This is a RADIUS client, should go under Microsoft_Radius_Protocol/Children/Clients/Children
                parent_path = "./Children/Microsoft_Internet_Authentication_Service/Children/Protocols/Children/Microsoft_Radius_Protocol/Children/Clients/Children"
                parents = base_root.findall(parent_path)
                if parents:
                    return parents[0]
    
    # If we couldn't determine the specific location, try to find by tag pattern matching
    if element_tag.endswith("_network_mgmt_") or "_Cisco_" in element_tag or "Wireless" in element_tag:
        # This is likely a profile, try profiles location
        parent_path = "./Children/Microsoft_Internet_Authentication_Service/Children/RadiusProfiles/Children"
        parents = base_root.findall(parent_path)
        if parents:
            return parents[0]
    
    # Fall back to root Children as last resort
    parents = base_root.findall("./Children")
    if parents:
        return parents[0]
    
    # If all else fails, return the root
    return base_root

def merge_nps_files(input_files, output_file):
    """
    Merge multiple NPS XML files, preserving hierarchy and deduplicating elements.
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
            for child in elem:
                if child.tag == "Properties":
                    key = get_element_id(elem)
                    seen_elements[key] = elem
                    break
        
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
                for parent in merge_root.findall(".//*"):
                    for child in parent:
                        if child.tag == "Properties":
                            elements_with_properties.append(parent)
                            break
                
                print(f"  Found {len(elements_with_properties)} elements with Properties in {file_path}")
                
                # For each element with Properties, find its correct location in the base file
                for element in elements_with_properties:
                    # Create a unique identifier for this element
                    key = get_element_id(element)
                    
                    # Skip if we've already seen this element
                    if key in seen_elements:
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
            
            print(f"Successfully merged NPS files into {output_file}")
            return True
        
        except Exception as e:
            print(f"Error writing output file: {str(e)}")
            return False
    
    except Exception as e:
        print(f"Error during merge process: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    parser = argparse.ArgumentParser(description='Merge Windows NPS XML files with hierarchy preservation')
    parser.add_argument('input_files', nargs='+', help='Input NPS XML files to merge')
    parser.add_argument('-o', '--output', default='merged_nps.xml', help='Output file (default: merged_nps.xml)')
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
        print("Error: No valid NPS XML files to merge")
        return 1
    
    # Perform the merge
    success = merge_nps_files(valid_files, args.output)
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())