#! /usr/bin/env python
import os
import sys
import subprocess
import tempfile
import shutil


#######################################
# Manifest processing

import xml.etree.ElementTree
import re

def process_value(rv):
    attrs = rv.attrib
    name = attrs["name"]
    value = attrs["value"]
    value_type = attrs["valueType"]
    if not name.strip():
        name = "@"
    else:
        name = "\"%s\"" % name
    if value_type == 'REG_BINARY':
        value = re.findall('..',value)
        value = 'hex:'+",".join(value)
    elif value_type == 'REG_DWORD':
        value = "dword:%s" % value.replace("0x", "")
    elif value_type == 'REG_NONE':
        value = None
    elif value_type == 'REG_EXPAND_SZ':
        value = value.replace("%SystemRoot%", "C:\\windows")
        value = "\"%s\"" % value
    elif value_type == 'REG_SZ':
        value = "\"%s\"" % value
    else:
        print("warning unkown type: %s" % value_type)
        value = "\"%s\"" % value
    if value:
        value = value.replace("$(runtime.system32)", "C:\\windows\\System32")
        value = value.replace("\\", "\\\\")
    return name, value

def process_key(key):
    key = key.strip("\\")
    key = key.replace("HKEY_CLASSES_ROOT", "HKEY_LOCAL_MACHINE\\Software\\Classes")
    return key

def process_manifest(file_name):
    out = ""
    e = xml.etree.ElementTree.parse(file_name).getroot()
    registry_keys = e.findall("{urn:schemas-microsoft-com:asm.v3}registryKeys")
    if len(registry_keys):
        for registry_key in registry_keys[0].getchildren():
            key = process_key(registry_key.attrib["keyName"])
            out += "[%s]\n" % key
            for rv in registry_key.findall("{urn:schemas-microsoft-com:asm.v3}registryValue"):
                name, value = process_value(rv)
                if not value is None:
                    out += "%s=%s\n"%(name,value)
            out += "\n"
    return out


#######################################
# Installer Processing

def extract_from_installer(orig_file, dest_dir, component):
    filter_str = "*%s*" % component
    print("%s" % component.strip("_"))
    cmd = ["cabextract", "-F", filter_str, "-d", dest_dir, orig_file]
    subprocess.check_output(cmd)
    output_files = [os.path.join(r,file) for r,d,f in os.walk(dest_dir) for file in f]
    return output_files

def load_manifest(file_path):
    file_name = os.path.basename(file_path)
    print("- %s" % file_name)
    return process_manifest(file_path)

def install_dll(dll_path):
    file_name = os.path.basename(dll_path)
    print("- %s -> %s" % (file_name, system32_path))
    shutil.copy(dll_path, system32_path)

def install_regfile(path, reg_file):
    cmd = [winebin, "regedit", os.path.join(path, reg_file)]
    subprocess.call(cmd)

def process_files(output_files):
    out = "Windows Registry Editor Version 5.00\n\n"
    for file_path in output_files:
        if file_path.endswith(".manifest"):
            out += load_manifest(file_path)

    for file_path in output_files:
        if file_path.endswith(".dll"):
            install_dll(file_path)

    with open(os.path.join(tmpdir, "full.reg"), "w") as f:
        f.write(out)
    install_regfile(tmpdir, "full.reg")

def find_wineprefix_arch(prefix_path):
    system_reg_file = os.path.join(prefix_path, 'user.reg')
    with open(system_reg_file) as f:
        for line in system_reg_file.readlines():
            if line.startswith("#arch=win32"):
                # ok
                return 'win32'
            elif line.startswith("#arch=win64"):
                print("64 bit prefix not supported yet!")
                sys.exit(1)
        print("Could not determine wineprefix arch!")
        sys.exit(1)

#######################################
# Main

if __name__ == '__main__':
    # sanity checks
    if len(sys.argv) < 3:
        print("usage:")
        print("  cabinstall.py cabfile component [wineprefix_path] [wine]")
        print("")
        print("example:")
        print("  cabinstall.py ~/.cache/winetricks/win7sp1/windows6.1-KB976932-X86.exe x86_microsoft-windows-mediafoundation")
        print("")
        sys.exit(0)
    if len(sys.argv) < 4 and not "WINEPREFIX" in os.environ:
        print("You need to set WINEPREFIX for this to work!")
        sys.exit(1)

    # setup
    if len(sys.argv) < 4:
        wineprefix = os.environ["WINEPREFIX"]
    else:
        wineprefix = sys.argv[3]

    check_wineprefix_arch(wineprefix)

    if len(sys.argv) == 5:
        winebin = sys.argv[4]
    else:
        winebin = "wine"

    system32_path = os.path.join(wineprefix, 'drive_c', 'windows', 'system32')

    tmpdir = tempfile.mkdtemp()
    cabfile = sys.argv[1]
    component = sys.argv[2]

    # processing
    output_files = extract_from_installer(cabfile, tmpdir, component)
    process_files(output_files)

    # clean up
    shutil.rmtree(tmpdir)

