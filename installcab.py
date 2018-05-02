#! /usr/bin/env python
import os
import sys
import subprocess
import tempfile
import shutil


#######################################
# Utils

def cleanup():
    shutil.rmtree(tmpdir)

def bad_exit(text):
    print(text)
    cleanup()
    sys.exit(1)

#######################################
# Architecture helpers

arch_map = {
    "amd64": "win64",
    "x86": "win32",
    "wow64": "wow64"
}

dest_map = {
    "win64:win32": "Syswow64",
    "win64:win64": "System32",
    "win64:wow64": "System32",
    "win32:win32": "System32"
}

def check_wineprefix_arch(prefix_path):
    system_reg_file = os.path.join(prefix_path, 'user.reg')
    with open(system_reg_file) as f:
        for line in f.readlines():
            if line.startswith("#arch=win32"):
                # ok
                return 'win32'
            elif line.startswith("#arch=win64"):
                return 'win64'
        bad_exit("Could not determine wineprefix arch!")

def get_system32_realdir(arch):
    return dest_map[winearch+':'+arch]

def get_dll_destdir(dll_path):
    arch = check_dll_arch(dll_path)
    if arch == 'win32' and winearch == 'win64':
        dest_dir = syswow64_path
    elif arch == 'win64' and winearch == 'win32':
        bad_exit("Invalid win64 assembly for win32 wineprefix!")
    else:
        dest_dir = system32_path
    return dest_dir

def get_winebin(arch):
    if (arch == 'win64' or arch == 'wow64') and winearch == 'win32':
        bad_exit("Invalid win64 assembly for win32 wineprefix!")
    elif arch == 'win32' or arch == 'wow64':
        winebin = 'wine'
    else:
        winebin = 'wine64'
    return winebin

def check_dll_arch(dll_path):
    out = subprocess.check_output(['file', dll_path])
    if 'x86-64' in out:
        return 'win64'
    else:
        return 'win32'

#######################################
# Manifest processing

import xml.etree.ElementTree
import re

def process_value(rv, arch):
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
        value = value.replace("$(runtime.system32)", "C:\\windows\\%s" % get_system32_realdir(arch))
        value = value.replace("\\", "\\\\")
    return name, value

def process_key(key):
    key = key.strip("\\")
    key = key.replace("HKEY_CLASSES_ROOT", "HKEY_LOCAL_MACHINE\\Software\\Classes")
    return key

def parse_manifest_arch(elmt):
    registry_keys = elmt.findall("{urn:schemas-microsoft-com:asm.v3}assemblyIdentity")
    if not len(registry_keys):
        bad_exit("Can't find processor architecture")
    arch = registry_keys[0].attrib["processorArchitecture"]
    if not arch in arch_map:
        bad_exit("Unknown processor architecture %s" % arch)
    arch = arch_map[arch]
    if (arch == 'win64' or arch == 'wow64') and winearch == 'win32':
        bad_exit("Invalid 64 bit assembly for 32 bit system!")
    return arch

def process_manifest(file_name):
    out = ""
    elmt = xml.etree.ElementTree.parse(file_name).getroot()
    arch = parse_manifest_arch(elmt)
    registry_keys = elmt.findall("{urn:schemas-microsoft-com:asm.v3}registryKeys")
    if len(registry_keys):
        for registry_key in registry_keys[0].getchildren():
            key = process_key(registry_key.attrib["keyName"])
            out += "[%s]\n" % key
            for rv in registry_key.findall("{urn:schemas-microsoft-com:asm.v3}registryValue"):
                name, value = process_value(rv, arch)
                if not value is None:
                    out += "%s=%s\n"%(name,value)
            out += "\n"
    return (out, arch)


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
    reg_data, arch = process_manifest(file_path)
    print("- %s (%s)" % (file_name, arch))
    return reg_data, arch

def install_dll(dll_path):
    dest_dir = get_dll_destdir(dll_path)
    file_name = os.path.basename(dll_path)
    print("- %s -> %s" % (file_name, dest_dir))
    shutil.copy(dll_path, dest_dir)

def install_regfile(path, reg_file, arch):
    winebin = get_winebin(arch)
    # print("  install reg with %s" % winebin)
    cmd = [winebin, "regedit", os.path.join(path, reg_file)]
    subprocess.call(cmd)

def process_files(output_files):
    reg_files = []
    for file_path in output_files:
        if file_path.endswith(".manifest"):
            out = "Windows Registry Editor Version 5.00\n\n"
            outdata, arch = load_manifest(file_path)
            out += outdata
            # print("  %s assembly" % arch)
            with open(os.path.join(tmpdir, file_path+".reg"), "w") as f:
                f.write(out)
            reg_files.append((file_path, arch))

    for file_path in output_files:
        if file_path.endswith(".dll"):
            install_dll(file_path)

    for file_path, arch in reg_files:
        install_regfile(tmpdir, file_path+".reg", arch)

#######################################
# Main

if __name__ == '__main__':
    # sanity checks
    if len(sys.argv) < 3:
        print("usage:")
        print("  cabinstall.py cabfile component [wineprefix_path]")
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

    winearch = check_wineprefix_arch(wineprefix)

    system32_path = os.path.join(wineprefix, 'drive_c', 'windows', 'system32')
    syswow64_path = os.path.join(wineprefix, 'drive_c', 'windows', 'syswow64')

    tmpdir = tempfile.mkdtemp()
    cabfile = sys.argv[1]
    component = sys.argv[2]

    # processing
    output_files = extract_from_installer(cabfile, tmpdir, component)
    process_files(output_files)

    # clean up
    cleanup()

